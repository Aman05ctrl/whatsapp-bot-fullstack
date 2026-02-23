import * as XLSX from 'xlsx';

export function exportToExcel(
  data: any[],
  filename: string,
  sheetName: string = 'Sheet1'
): void {
  // Create workbook
  const wb = XLSX.utils.book_new();
  
  // Create worksheet from data
  const ws = XLSX.utils.json_to_sheet(data);
  
  // Auto-size columns
  const cols = Object.keys(data[0] || {}).map(key => ({
    wch: Math.max(
      key.length,
      ...data.map(row => String(row[key] || '').length)
    ) + 2
  }));
  ws['!cols'] = cols;
  
  // Add worksheet to workbook
  XLSX.utils.book_append_sheet(wb, ws, sheetName);
  
  // Generate file and trigger download
  XLSX.writeFile(wb, `${filename}.xlsx`);
}