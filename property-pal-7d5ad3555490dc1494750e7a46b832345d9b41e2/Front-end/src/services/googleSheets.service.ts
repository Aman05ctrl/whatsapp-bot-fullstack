function getStorageKey(): string {
  const token = localStorage.getItem('auth_token');
  if (!token) return 'sheets_config';
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return `sheets_config_${payload.email}`;
  } catch {
    return 'sheets_config';
  }
}

export interface SheetsConfig {
  sheetId: string;
  apiKey: string;
}

export interface Lead {
  created_at: string;
  name: string;
  country_code: string;
  phone: string;
  interest: string;
  email: string;
  city: string;
  last_updated: string;
  raw_id: string;
  lead_score: number;
  lead_status: string;
  follow_up_due: string;
  lead_summary: string;
  budget_category: string;
  agent_handover: string;
  conversation_status: string;
  user_fingerprint: string;
}

export interface BotLog {
  timestamp: string;
  user_name: string;
  country_code: string;
  phone: string;
  user_message: string;
  reply_type: string;
  bot_response: string;
}

export function getSheetsConfig(): SheetsConfig | null {
  const stored = localStorage.getItem(getStorageKey());
  return stored ? JSON.parse(stored) : null;
}

export function setSheetsConfig(config: SheetsConfig) {
  localStorage.setItem(getStorageKey(), JSON.stringify(config));
}

async function fetchSheetData(sheetName: string): Promise<any[][]> {
  const config = getSheetsConfig();
  if (!config) throw new Error('Google Sheets not configured');

  const url = `https://sheets.googleapis.com/v4/spreadsheets/${config.sheetId}/values/${sheetName}?key=${config.apiKey}`;
  
  const response = await fetch(url);
if (!response.ok) {
  const err = await response.json().catch(() => ({}));
  throw new Error(err?.error?.message || `Failed to fetch ${sheetName}: ${response.status}`);
}
  
  const data = await response.json();
  return data.values || [];
}

export async function getLeads(): Promise<Lead[]> {
  const rows = await fetchSheetData('Profiles');
  if (rows.length < 2) return [];
  
  const headers = rows[0];
  return rows.slice(1).map(row => ({
    created_at: row[0] || '',
    name: row[1] || '',
    country_code: row[2] || '',
    phone: row[3] || '',
    interest: row[4] || '',
    email: row[5] || '',
    city: row[6] || '',
    last_updated: row[7] || '',
    raw_id: row[8] || '',
    lead_score: parseInt(row[9]) || 0,
    lead_status: row[10] || '',
    follow_up_due: row[11] || '',
    lead_summary: row[12] || '',
    budget_category: row[13] || '',
    agent_handover: row[14] || '',
    conversation_status: row[15] || '',
    user_fingerprint: row[16] || '',
  }));
}

export async function getLogs(): Promise<BotLog[]> {
  const rows = await fetchSheetData('Logs');
  if (rows.length < 2) return [];
  
  return rows.slice(1).map(row => ({
    timestamp: row[0] || '',
    user_name: row[1] || '',
    country_code: row[2] || '',
    phone: row[3] || '',
    user_message: row[4] || '',
    reply_type: row[5] || '',
    bot_response: row[6] || '',
  }));
}