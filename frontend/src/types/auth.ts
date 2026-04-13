export interface AuthUser {
  id: string;
  email: string;
  is_global_admin: boolean;
  role?: string;
}
