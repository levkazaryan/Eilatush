// Lightweight token storage with AsyncStorage (works on web + native).
// On web, AsyncStorage falls back to localStorage which is fine for this MVP.
import AsyncStorage from "@react-native-async-storage/async-storage";

const TOKEN_KEY = "eilatush_vip_token_v1";
const MEMBER_KEY = "eilatush_vip_member_v1";

export type VIPMember = {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  dob: string;
  address: string;
  member_number: string;
  join_date: string;
  expiry_date: string;
  is_active: boolean;
  is_admin?: boolean;
  last_login?: string | null;
  created_at?: string | null;
};

export async function saveAuth(token: string, member: VIPMember) {
  try {
    await AsyncStorage.setItem(TOKEN_KEY, token);
    await AsyncStorage.setItem(MEMBER_KEY, JSON.stringify(member));
  } catch (e) {
    console.warn("saveAuth failed", e);
  }
}

export async function loadAuth(): Promise<{ token: string | null; member: VIPMember | null }> {
  try {
    const [token, raw] = await Promise.all([
      AsyncStorage.getItem(TOKEN_KEY),
      AsyncStorage.getItem(MEMBER_KEY),
    ]);
    const member = raw ? (JSON.parse(raw) as VIPMember) : null;
    return { token, member };
  } catch (e) {
    console.warn("loadAuth failed", e);
    return { token: null, member: null };
  }
}

export async function clearAuth() {
  try {
    await AsyncStorage.multiRemove([TOKEN_KEY, MEMBER_KEY]);
  } catch (e) {
    console.warn("clearAuth failed", e);
  }
}
