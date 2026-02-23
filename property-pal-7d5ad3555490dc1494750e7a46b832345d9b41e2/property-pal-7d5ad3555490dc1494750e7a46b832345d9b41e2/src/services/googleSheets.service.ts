// const STORAGE_KEY = 'sheets_config';

// export interface SheetsConfig {
//   sheetId: string;
//   apiKey: string;
// }

// export function getSheetsConfig(): SheetsConfig | null {
//   try {
//     const raw = localStorage.getItem(STORAGE_KEY);
//     return raw ? JSON.parse(raw) : null;
//   } catch {
//     return null;
//   }
// }

// export function saveSheetsConfig(config: SheetsConfig) {
//   localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
// }

// async function fetchSheet(sheetName: string): Promise<string[][]> {
//   const config = getSheetsConfig();
//   if (!config) throw new Error('Google Sheets not configured');

//   const url = `https://sheets.googleapis.com/v4/spreadsheets/${config.sheetId}/values/${encodeURIComponent(sheetName)}?key=${config.apiKey}`;
//   const res = await fetch(url);
//   if (!res.ok) {
//     const err = await res.json().catch(() => ({}));
//     throw new Error(err?.error?.message || `Sheets API error: ${res.status}`);
//   }
//   const data = await res.json();
//   return data.values || [];
// }

// function rowsToObjects(rows: string[][]): Record<string, string>[] {
//   if (rows.length < 2) return [];
//   const headers = rows[0];
//   return rows.slice(1).map(row => {
//     const obj: Record<string, string> = {};
//     headers.forEach((h, i) => {
//       obj[h] = row[i] || '';
//     });
//     return obj;
//   });
// }

// export interface Lead {
//   created_at: string;
//   name: string;
//   country_code: string;
//   phone: string;
//   interest: string;
//   email: string;
//   city: string;
//   last_updated: string;
//   raw_id: string;
//   lead_score: number;
//   lead_status: string;
//   follow_up_due: string;
//   lead_summary: string;
//   budget_category: string;
//   agent_handover: string;
//   conversation_status: string;
//   user_fingerprint: string;
// }

// export async function getProfiles(): Promise<Lead[]> {
//   const rows = await fetchSheet('Profiles');
//   return rowsToObjects(rows).map(r => ({
//     created_at: r['Created At'] || '',
//     name: r['Name'] || '',
//     country_code: r['Country Code'] || '',
//     phone: r['Phone Number'] || '',
//     interest: r['Interest'] || '',
//     email: r['Email'] || '',
//     city: r['City'] || '',
//     last_updated: r['Last Updated'] || '',
//     raw_id: r['Raw ID'] || '',
//     lead_score: parseInt(r['Lead Score']) || 0,
//     lead_status: r['Lead Status'] || '',
//     follow_up_due: r['Follow-Up Due'] || '',
//     lead_summary: r['Lead Summary'] || '',
//     budget_category: r['Budget Category'] || '',
//     agent_handover: r['Agent Handover'] || '',
//     conversation_status: r['Conversation Status'] || '',
//     user_fingerprint: r['User_Fingerprint'] || '',
//   }));
// }

// export interface BotLog {
//   timestamp: string;
//   user_name: string;
//   country_code: string;
//   phone: string;
//   user_message: string;
//   reply_type: string;
//   bot_response: string;
// }

// export async function getLogs(): Promise<BotLog[]> {
//   const rows = await fetchSheet('Logs');
//   return rowsToObjects(rows).map(r => ({
//     timestamp: r['Timestamp'] || '',
//     user_name: r['User Name'] || '',
//     country_code: r['Country Code'] || '',
//     phone: r['Phone'] || '',
//     user_message: r['User Message'] || '',
//     reply_type: r['Reply Type'] || '',
//     bot_response: r['Bot Response'] || '',
//   }));
// }


const STORAGE_KEY = 'sheets_config';

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
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored ? JSON.parse(stored) : null;
}

export function setSheetsConfig(config: SheetsConfig) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
}

async function fetchSheetData(sheetName: string): Promise<any[][]> {
  const config = getSheetsConfig();
  if (!config) throw new Error('Google Sheets not configured');

  const url = `https://sheets.googleapis.com/v4/spreadsheets/${config.sheetId}/values/${sheetName}?key=${config.apiKey}`;
  
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${sheetName}: ${response.statusText}`);
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