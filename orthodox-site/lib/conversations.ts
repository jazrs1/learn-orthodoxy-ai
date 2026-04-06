import "server-only";

import { PoolClient } from "pg";
import { ChatBackendHistoryMessage, ChatMessage, ConversationDetail, ConversationSummary, SourceRef } from "./chat-types";
import { query, withTransaction } from "./db";

type ConversationRow = {
  id: string;
  title: string;
  created_at: Date;
  updated_at: Date;
};

type MessageRow = {
  id: string;
  role: "user" | "assistant";
  content: string;
  entities: string[] | null;
  options: string[] | null;
  sources: SourceRef[] | null;
  created_at: Date;
};

function conversationSummaryFromRow(row: ConversationRow): ConversationSummary {
  return {
    id: row.id,
    title: row.title,
    createdAt: row.created_at.toISOString(),
    updatedAt: row.updated_at.toISOString(),
  };
}

function messageFromRow(row: MessageRow): ChatMessage {
  return {
    id: row.id,
    role: row.role,
    content: row.content,
    entities: Array.isArray(row.entities) ? row.entities : [],
    options: Array.isArray(row.options) ? row.options : [],
    sources: Array.isArray(row.sources) ? row.sources : [],
    createdAt: row.created_at.toISOString(),
  };
}

function deriveConversationTitle(question: string) {
  const trimmed = question.trim();
  if (!trimmed) return "New Chat";
  return trimmed.length > 70 ? `${trimmed.slice(0, 67)}...` : trimmed;
}

export async function listConversations(sessionId: string): Promise<ConversationSummary[]> {
  const result = await query<ConversationRow>(
    `
      select id, title, created_at, updated_at
      from chat_conversations
      where session_id = $1
        and archived_at is null
      order by updated_at desc
    `,
    [sessionId]
  );

  return result.rows.map(conversationSummaryFromRow);
}

export async function getConversation(
  sessionId: string,
  conversationId: string
): Promise<ConversationDetail | null> {
  const conversationResult = await query<ConversationRow>(
    `
      select id, title, created_at, updated_at
      from chat_conversations
      where id = $1
        and session_id = $2
        and archived_at is null
      limit 1
    `,
    [conversationId, sessionId]
  );

  const conversation = conversationResult.rows[0];
  if (!conversation) return null;

  const messagesResult = await query<MessageRow>(
    `
      select id, role, content, entities, options, sources, created_at
      from chat_messages
      where conversation_id = $1
      order by sort_order asc
    `,
    [conversationId]
  );

  return {
    ...conversationSummaryFromRow(conversation),
    messages: messagesResult.rows.map(messageFromRow),
  };
}

export async function createConversation(sessionId: string, title = "New Chat") {
  const conversationId = crypto.randomUUID();
  const result = await query<ConversationRow>(
    `
      insert into chat_conversations (id, session_id, title)
      values ($1, $2, $3)
      returning id, title, created_at, updated_at
    `,
    [conversationId, sessionId, title]
  );

  return conversationSummaryFromRow(result.rows[0]);
}

export async function archiveConversation(sessionId: string, conversationId: string) {
  await query(
    `
      update chat_conversations
      set archived_at = now(),
          updated_at = now()
      where id = $1
        and session_id = $2
    `,
    [conversationId, sessionId]
  );
}

async function getNextSortOrder(client: PoolClient, conversationId: string) {
  const result = await client.query<{ next_sort_order: number }>(
    `
      select coalesce(max(sort_order), 0) + 1 as next_sort_order
      from chat_messages
      where conversation_id = $1
    `,
    [conversationId]
  );

  return result.rows[0]?.next_sort_order ?? 1;
}

async function insertMessage(
  client: PoolClient,
  conversationId: string,
  message: ChatMessage,
  sortOrder: number
) {
  await client.query(
    `
      insert into chat_messages (
        id, conversation_id, role, content, entities, options, sources, sort_order
      )
      values ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb, $8)
    `,
    [
      message.id,
      conversationId,
      message.role,
      message.content,
      JSON.stringify(message.entities || []),
      JSON.stringify(message.options || []),
      JSON.stringify(message.sources || []),
      sortOrder,
    ]
  );
}

export async function getRecentHistory(
  sessionId: string,
  conversationId: string,
  limit = 6
): Promise<ChatBackendHistoryMessage[]> {
  const result = await query<{ role: "user" | "assistant"; content: string }>(
    `
      select role, content
      from chat_messages
      where conversation_id = $1
        and exists (
          select 1 from chat_conversations
          where id = $1
            and session_id = $2
            and archived_at is null
        )
      order by sort_order desc
      limit $3
    `,
    [conversationId, sessionId, limit]
  );

  return result.rows.reverse();
}

export async function saveChatTurn({
  sessionId,
  conversationId,
  question,
  assistantMessage,
}: {
  sessionId: string;
  conversationId?: string;
  question: string;
  assistantMessage: Omit<ChatMessage, "role">;
}) {
  return withTransaction(async (client) => {
    let conversation = conversationId
      ? await client.query<ConversationRow>(
          `
            select id, title, created_at, updated_at
            from chat_conversations
            where id = $1
              and session_id = $2
              and archived_at is null
            limit 1
          `,
          [conversationId, sessionId]
        ).then((result) => result.rows[0] || null)
      : null;

    if (!conversation) {
      const created = await client.query<ConversationRow>(
        `
          insert into chat_conversations (id, session_id, title)
          values ($1, $2, $3)
          returning id, title, created_at, updated_at
        `,
        [crypto.randomUUID(), sessionId, deriveConversationTitle(question)]
      );
      conversation = created.rows[0];
    }

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
      entities: [],
      options: [],
      sources: [],
    };

    const firstSortOrder = await getNextSortOrder(client, conversation.id);
    await insertMessage(client, conversation.id, userMessage, firstSortOrder);
    await insertMessage(
      client,
      conversation.id,
      { ...assistantMessage, role: "assistant" },
      firstSortOrder + 1
    );

    const updatedConversation = await client.query<ConversationRow>(
      `
        update chat_conversations
        set title = case
              when title = 'New Chat' then $2
              else title
            end,
            updated_at = now()
        where id = $1
        returning id, title, created_at, updated_at
      `,
      [conversation.id, deriveConversationTitle(question)]
    );

    return {
      conversation: conversationSummaryFromRow(updatedConversation.rows[0]),
      userMessage,
      assistantMessage: {
        ...assistantMessage,
        role: "assistant" as const,
      },
    };
  });
}
