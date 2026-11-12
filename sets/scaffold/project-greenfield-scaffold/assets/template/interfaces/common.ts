// Cross-domain shared shapes.

export interface SessionUser {
  id: string | null;
  email: string | null;
  name: string | null;
  image?: string | null;
  createdAt: string | null;
}
