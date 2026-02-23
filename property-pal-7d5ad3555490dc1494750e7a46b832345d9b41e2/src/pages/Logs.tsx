import { useEffect, useState, useMemo, useCallback } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import {
  MessageSquare, Search, Download, AlertCircle, RefreshCw, List, MessageCircle,
} from 'lucide-react';
import { getLogs, BotLog, getSheetsConfig } from '@/services/googleSheets.service';
import { exportToExcel } from '@/services/export.service';
import { toast } from '@/hooks/use-toast';

function ReplyTypeBadge({ type }: { type: string }) {
  const t = type.toLowerCase();
  if (t === 'template') return <span className="status-badge bg-primary/20 text-primary">Template</span>;
  if (t === 'ai') return <span className="status-badge bg-accent/20 text-accent">AI</span>;
  if (t === 'fallback') return <span className="status-badge bg-destructive/20 text-destructive">Fallback</span>;
  return <span className="status-inactive">{type}</span>;
}

export default function Logs() {
  const [logs, setLogs] = useState<BotLog[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [replyFilter, setReplyFilter] = useState('all');
  const [viewMode, setViewMode] = useState<'table' | 'chat'>('table');
  const [selectedPhone, setSelectedPhone] = useState<string>('');
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  const config = getSheetsConfig();

  const fetchLogs = useCallback(async () => {
    if (!config) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await getLogs();
      setLogs(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load logs');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  const filteredLogs = useMemo(() => {
    return logs.filter(l => {
      if (search) {
        const q = search.toLowerCase();
        if (!l.user_name.toLowerCase().includes(q) && !l.phone.includes(q) && !l.user_message.toLowerCase().includes(q)) return false;
      }
      if (replyFilter !== 'all' && l.reply_type.toLowerCase() !== replyFilter.toLowerCase()) return false;
      return true;
    });
  }, [logs, search, replyFilter]);

  const stats = useMemo(() => ({
    total: logs.length,
    template: logs.filter(l => l.reply_type.toLowerCase() === 'template').length,
    ai: logs.filter(l => l.reply_type.toLowerCase() === 'ai').length,
    fallback: logs.filter(l => l.reply_type.toLowerCase() === 'fallback').length,
  }), [logs]);

  const phones = useMemo(() => [...new Set(logs.map(l => l.phone).filter(Boolean))], [logs]);
  const chatLogs = useMemo(() => {
    const phone = selectedPhone || phones[0] || '';
    return logs.filter(l => l.phone === phone);
  }, [logs, selectedPhone, phones]);

  const handleExport = () => {
    exportToExcel(
      filteredLogs.map(l => ({
        Timestamp: l.timestamp, User: l.user_name, Phone: l.phone,
        Message: l.user_message, 'Reply Type': l.reply_type, Response: l.bot_response,
      })),
      `bot_logs_${new Date().toISOString().split('T')[0]}`,
      'Logs'
    );
    toast({ title: 'Logs exported' });
  };

  if (!config) {
    return (
      <DashboardLayout>
        <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
          <MessageSquare className="h-16 w-16 text-muted-foreground/30 mb-4" />
          <h2 className="text-xl font-semibold mb-2">Configure Google Sheets</h2>
          <p className="text-muted-foreground text-sm mb-6 text-center max-w-md">
            Set up Google Sheets on the Leads page first to view bot logs.
          </p>
          <Button asChild><a href="/leads">Go to Leads</a></Button>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6 animate-fade-in">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="page-header text-3xl">Bot Conversation Logs</h1>
            <p className="text-muted-foreground text-sm mt-1">Monitor all WhatsApp bot interactions</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={handleExport}><Download className="h-4 w-4 mr-1" />Export</Button>
            <Button variant="outline" size="sm" onClick={fetchLogs}><RefreshCw className="h-4 w-4 mr-1" />Refresh</Button>
          </div>
        </div>

        {error && <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}

        {/* Stats */}
        <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
          {[
            { label: 'Total Conversations', value: stats.total, icon: MessageSquare },
            { label: 'Template Replies', value: stats.template, icon: MessageCircle },
            { label: 'AI Replies', value: stats.ai, icon: MessageCircle },
            { label: 'Fallback (Review)', value: stats.fallback, icon: AlertCircle },
          ].map((s, i) => (
            <Card key={i} className="card-elevated glow-border">
              <CardContent className="p-4">
                <s.icon className="h-4 w-4 text-primary mb-1" />
                <p className="text-2xl font-bold">{s.value}</p>
                <p className="text-xs text-muted-foreground">{s.label}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Filters + View Toggle */}
        <div className="flex flex-wrap gap-3 items-center">
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input className="pl-9" placeholder="Search logs..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <Select value={replyFilter} onValueChange={setReplyFilter}>
            <SelectTrigger className="w-[140px]"><SelectValue placeholder="Reply Type" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              <SelectItem value="template">Template</SelectItem>
              <SelectItem value="ai">AI</SelectItem>
              <SelectItem value="fallback">Fallback</SelectItem>
            </SelectContent>
          </Select>
          <div className="flex gap-1 border border-border rounded-lg p-1">
            <Button variant={viewMode === 'table' ? 'secondary' : 'ghost'} size="sm" onClick={() => setViewMode('table')}>
              <List className="h-4 w-4 mr-1" />Table
            </Button>
            <Button variant={viewMode === 'chat' ? 'secondary' : 'ghost'} size="sm" onClick={() => setViewMode('chat')}>
              <MessageCircle className="h-4 w-4 mr-1" />Chat
            </Button>
          </div>
        </div>

        {isLoading ? (
          <div className="space-y-2">{[1,2,3,4].map(i => <Skeleton key={i} className="h-12 rounded-lg" />)}</div>
        ) : viewMode === 'table' ? (
          <Card className="card-elevated glow-border overflow-hidden">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Time</TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>Phone</TableHead>
                    <TableHead>Message</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Response</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredLogs.map((log, i) => (
                    <TableRow
                      key={i}
                      className="hover:bg-primary/5 cursor-pointer transition-colors"
                      onClick={() => setExpandedRow(expandedRow === i ? null : i)}
                    >
                      <TableCell className="text-xs text-muted-foreground whitespace-nowrap">{log.timestamp}</TableCell>
                      <TableCell className="text-sm font-medium">{log.user_name}</TableCell>
                      <TableCell className="text-sm font-mono">{log.phone}</TableCell>
                      <TableCell className="text-sm max-w-[200px] truncate">{log.user_message}</TableCell>
                      <TableCell><ReplyTypeBadge type={log.reply_type} /></TableCell>
                      <TableCell className="text-sm max-w-[250px]">
                        {expandedRow === i ? (
                          <div className="whitespace-pre-wrap text-xs bg-muted/50 p-2 rounded-lg max-h-40 overflow-y-auto">{log.bot_response}</div>
                        ) : (
                          <span className="truncate block">{log.bot_response?.slice(0, 60)}...</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Card>
        ) : (
          /* Chat View */
          <Card className="card-elevated glow-border">
            <CardHeader className="pb-2">
              <div className="flex items-center gap-3">
                <Select value={selectedPhone || phones[0] || ''} onValueChange={setSelectedPhone}>
                  <SelectTrigger className="w-[200px]"><SelectValue placeholder="Select user" /></SelectTrigger>
                  <SelectContent>
                    {phones.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 max-h-[500px] overflow-y-auto p-2">
                {chatLogs.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-8">No messages</p>
                ) : chatLogs.map((log, i) => (
                  <div key={i} className="space-y-2">
                    <p className="text-[10px] text-muted-foreground text-center">{log.timestamp}</p>
                    {/* User message */}
                    <div className="flex justify-start">
                      <div className="max-w-[75%] rounded-xl rounded-tl-none bg-muted px-3 py-2">
                        <p className="text-xs font-medium text-muted-foreground mb-0.5">{log.user_name}</p>
                        <p className="text-sm">{log.user_message}</p>
                      </div>
                    </div>
                    {/* Bot response */}
                    <div className="flex justify-end">
                      <div className="max-w-[75%] rounded-xl rounded-tr-none px-3 py-2" style={{ background: 'hsl(var(--primary) / 0.15)' }}>
                        <div className="flex items-center gap-1 mb-0.5">
                          <ReplyTypeBadge type={log.reply_type} />
                        </div>
                        <p className="text-sm whitespace-pre-wrap">{log.bot_response}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
