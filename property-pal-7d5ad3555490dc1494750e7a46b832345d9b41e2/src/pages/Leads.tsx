import { useEffect, useState, useMemo, useCallback } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from '@/components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import {
  Users, Search, Settings, RefreshCw, Download, AlertCircle, Eye, Copy, Phone,
} from 'lucide-react';
import { getProfiles, Lead, getSheetsConfig, saveSheetsConfig, SheetsConfig } from '@/services/googleSheets.service';
import { exportToExcel } from '@/services/export.service';
import { toast } from '@/hooks/use-toast';

function LeadScoreBadge({ score }: { score: number }) {
  if (score > 80) return <span className="status-badge bg-success/20 text-success">🔥 Boiling</span>;
  if (score > 60) return <span className="status-badge bg-primary/20 text-primary">Hot</span>;
  if (score > 30) return <span className="status-badge bg-accent/20 text-accent">Warm</span>;
  return <span className="status-badge bg-destructive/20 text-destructive">Cold</span>;
}

function LeadStatusBadge({ status }: { status: string }) {
  const s = status.toLowerCase();
  if (s === 'active') return <span className="status-available">{status}</span>;
  if (s === 'converted') return <span className="status-badge bg-primary/20 text-primary">{status}</span>;
  if (s === 'lost') return <span className="status-badge bg-destructive/20 text-destructive">{status}</span>;
  return <span className="status-inactive">{status || 'Unknown'}</span>;
}

export default function Leads() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [budgetFilter, setBudgetFilter] = useState('all');
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [configOpen, setConfigOpen] = useState(false);
  const [sheetId, setSheetId] = useState('');
  const [apiKey, setApiKey] = useState('');

  const config = getSheetsConfig();

  const fetchLeads = useCallback(async () => {
    if (!getSheetsConfig()) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await getProfiles();
      setLeads(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load leads');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchLeads(); }, [fetchLeads]);

  const filteredLeads = useMemo(() => {
    return leads.filter(l => {
      if (search) {
        const q = search.toLowerCase();
        if (!l.name.toLowerCase().includes(q) && !l.phone.includes(q) && !l.email.toLowerCase().includes(q) && !l.city.toLowerCase().includes(q)) return false;
      }
      if (statusFilter !== 'all' && l.lead_status.toLowerCase() !== statusFilter.toLowerCase()) return false;
      if (budgetFilter !== 'all' && l.budget_category !== budgetFilter) return false;
      return true;
    });
  }, [leads, search, statusFilter, budgetFilter]);

  const stats = useMemo(() => {
    const today = new Date().toISOString().split('T')[0];
    return {
      total: leads.length,
      active: leads.filter(l => l.lead_status.toLowerCase() === 'active').length,
      hot: leads.filter(l => l.lead_score > 70).length,
      followUpToday: leads.filter(l => l.follow_up_due.startsWith(today)).length,
    };
  }, [leads]);

  const handleSaveConfig = () => {
    if (!sheetId || !apiKey) return;
    saveSheetsConfig({ sheetId, apiKey });
    setConfigOpen(false);
    fetchLeads();
    toast({ title: 'Configuration saved' });
  };

  const handleExport = () => {
    const data = filteredLeads.map(l => ({
      Name: l.name, Phone: `${l.country_code}${l.phone}`, Email: l.email, City: l.city,
      Interest: l.interest, 'Lead Score': l.lead_score, Status: l.lead_status,
      'Follow-Up': l.follow_up_due, Budget: l.budget_category, Agent: l.agent_handover,
    }));
    exportToExcel(data, `leads_export_${new Date().toISOString().split('T')[0]}`, 'Leads');
    toast({ title: 'Export downloaded' });
  };

  const uniqueStatuses = useMemo(() => [...new Set(leads.map(l => l.lead_status).filter(Boolean))], [leads]);
  const uniqueBudgets = useMemo(() => [...new Set(leads.map(l => l.budget_category).filter(Boolean))], [leads]);

  if (!config) {
    return (
      <DashboardLayout>
        <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
          <Users className="h-16 w-16 text-muted-foreground/30 mb-4" />
          <h2 className="text-xl font-semibold mb-2">Configure Google Sheets</h2>
          <p className="text-muted-foreground text-sm mb-6 text-center max-w-md">
            Connect your Google Sheets to view leads from your WhatsApp bot.
          </p>
          <Dialog open={configOpen} onOpenChange={setConfigOpen}>
            <DialogTrigger asChild><Button><Settings className="h-4 w-4 mr-2" />Configure Sheets</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>Google Sheets Configuration</DialogTitle></DialogHeader>
              <div className="space-y-4 pt-2">
                <div><Label>Sheet ID</Label><Input value={sheetId} onChange={e => setSheetId(e.target.value)} placeholder="The long ID from your sheet URL" /></div>
                <div><Label>API Key</Label><Input value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="Google Sheets API Key" /></div>
                <Button onClick={handleSaveConfig} className="w-full">Save & Connect</Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6 animate-fade-in">
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="page-header text-3xl">Leads & CRM</h1>
            <p className="text-muted-foreground text-sm mt-1">{leads.length} total leads from WhatsApp bot</p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <Button variant="outline" size="sm" onClick={handleExport}><Download className="h-4 w-4 mr-1" />Export</Button>
            <Dialog open={configOpen} onOpenChange={setConfigOpen}>
              <DialogTrigger asChild><Button variant="outline" size="sm"><Settings className="h-4 w-4 mr-1" />Configure</Button></DialogTrigger>
              <DialogContent>
                <DialogHeader><DialogTitle>Google Sheets Configuration</DialogTitle></DialogHeader>
                <div className="space-y-4 pt-2">
                  <div><Label>Sheet ID</Label><Input value={sheetId || config?.sheetId || ''} onChange={e => setSheetId(e.target.value)} /></div>
                  <div><Label>API Key</Label><Input value={apiKey || config?.apiKey || ''} onChange={e => setApiKey(e.target.value)} /></div>
                  <Button onClick={handleSaveConfig} className="w-full">Save</Button>
                </div>
              </DialogContent>
            </Dialog>
            <Button variant="outline" size="sm" onClick={fetchLeads}><RefreshCw className="h-4 w-4 mr-1" />Refresh</Button>
          </div>
        </div>

        {error && <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}

        {/* Stats */}
        <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
          {[
            { label: 'Total Leads', value: stats.total, icon: Users },
            { label: 'Active', value: stats.active, icon: Users },
            { label: 'Hot Leads', value: stats.hot, icon: Phone },
            { label: 'Follow-up Today', value: stats.followUpToday, icon: RefreshCw },
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

        {/* Filters */}
        <div className="flex flex-wrap gap-3">
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input className="pl-9" placeholder="Search leads..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[140px]"><SelectValue placeholder="Status" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              {uniqueStatuses.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={budgetFilter} onValueChange={setBudgetFilter}>
            <SelectTrigger className="w-[140px]"><SelectValue placeholder="Budget" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Budget</SelectItem>
              {uniqueBudgets.map(b => <SelectItem key={b} value={b}>{b}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>

        {/* Table */}
        {isLoading ? (
          <div className="space-y-2">{[1,2,3,4,5].map(i => <Skeleton key={i} className="h-12 rounded-lg" />)}</div>
        ) : filteredLeads.length === 0 ? (
          <Card className="card-elevated"><CardContent className="py-12 text-center"><Users className="h-12 w-12 text-muted-foreground/30 mx-auto mb-3" /><p className="text-muted-foreground">No leads found</p></CardContent></Card>
        ) : (
          <Card className="card-elevated glow-border overflow-hidden">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Phone</TableHead>
                    <TableHead>Interest</TableHead>
                    <TableHead>City</TableHead>
                    <TableHead>Score</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Follow-Up</TableHead>
                    <TableHead>Budget</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredLeads.map((lead, i) => (
                    <TableRow key={i} className="hover:bg-primary/5 transition-colors">
                      <TableCell className="text-muted-foreground text-xs">{i + 1}</TableCell>
                      <TableCell className="font-medium text-sm">{lead.name}</TableCell>
                      <TableCell className="text-sm font-mono">{lead.country_code}{lead.phone}</TableCell>
                      <TableCell className="text-sm max-w-[150px] truncate">{lead.interest}</TableCell>
                      <TableCell className="text-sm">{lead.city}</TableCell>
                      <TableCell><LeadScoreBadge score={lead.lead_score} /></TableCell>
                      <TableCell><LeadStatusBadge status={lead.lead_status} /></TableCell>
                      <TableCell className="text-sm">{lead.follow_up_due || '—'}</TableCell>
                      <TableCell className="text-sm">{lead.budget_category || '—'}</TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="icon" onClick={() => setSelectedLead(lead)} title="View"><Eye className="h-3 w-3" /></Button>
                          <Button variant="ghost" size="icon" onClick={() => { navigator.clipboard.writeText(`${lead.country_code}${lead.phone}`); toast({ title: 'Phone copied' }); }} title="Copy phone"><Copy className="h-3 w-3" /></Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Card>
        )}

        {/* Lead Detail Modal */}
        <Dialog open={!!selectedLead} onOpenChange={(open) => !open && setSelectedLead(null)}>
          <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
            <DialogHeader><DialogTitle>{selectedLead?.name || 'Lead Details'}</DialogTitle></DialogHeader>
            {selectedLead && (
              <div className="space-y-4 pt-2">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  {[
                    ['Phone', `${selectedLead.country_code}${selectedLead.phone}`],
                    ['Email', selectedLead.email],
                    ['City', selectedLead.city],
                    ['Interest', selectedLead.interest],
                    ['Lead Score', `${selectedLead.lead_score}`],
                    ['Status', selectedLead.lead_status],
                    ['Budget', selectedLead.budget_category],
                    ['Agent', selectedLead.agent_handover],
                    ['Conv. Status', selectedLead.conversation_status],
                    ['Follow-Up', selectedLead.follow_up_due],
                    ['Created', selectedLead.created_at],
                    ['Updated', selectedLead.last_updated],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <p className="text-muted-foreground text-xs">{label}</p>
                      <p className="font-medium">{value || '—'}</p>
                    </div>
                  ))}
                </div>
                {selectedLead.lead_summary && (
                  <div>
                    <p className="text-muted-foreground text-xs mb-1">Lead Summary</p>
                    <p className="text-sm bg-muted/50 rounded-lg p-3 max-h-32 overflow-y-auto">{selectedLead.lead_summary}</p>
                  </div>
                )}
                <div>
                  <p className="text-muted-foreground text-xs mb-1">Fingerprint</p>
                  <p className="text-xs font-mono bg-muted/50 rounded-lg p-2 break-all">{selectedLead.user_fingerprint || '—'}</p>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => {
                    exportToExcel([selectedLead as any], `lead_${selectedLead.name}`, 'Lead');
                    toast({ title: 'Lead exported' });
                  }}>
                    <Download className="h-3 w-3 mr-1" />Export
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
}
