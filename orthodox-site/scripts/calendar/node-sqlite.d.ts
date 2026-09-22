// The site pins @types/node 20, which predates node:sqlite (Node 22.5+). This declares the one
// class the Katameros extractor uses, so the scripts type-check without upgrading the site's types.
declare module "node:sqlite" {
  export class DatabaseSync {
    constructor(path: string, options?: { readOnly?: boolean });
    prepare(sql: string): { all(...parameters: unknown[]): unknown[] };
    close(): void;
  }
}
