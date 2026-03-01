import { getMe } from "./api";
import type { User } from "@/types";

export async function getCurrentUser(): Promise<User | null> {
  try {
    return await getMe();
  } catch {
    return null;
  }
}
