import { useEffect, useState, useMemo, useCallback } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { getSheetsConfig, setSheetsConfig } from '@/services/googleSheets.service';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Users, Search, RefreshCw, Download, AlertCircle, Eye, Copy, Edit, Trash2, Loader2, Phone, Settings,
} from 'lucide-react';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
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
import { api, Lead, LeadUpdate, ApiError } from '@/lib/api';
import { toast } from 'sonner';

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

function SheetsConfigForm() {
  const [sheetId, setSheetId] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [config, setConfig] = useState(getSheetsConfig());

  const handleSave = () => {
    if (!sheetId && !apiKey) return;
    const newConfig = {
      sheetId: sheetId || config?.sheetId || '',
      apiKey: apiKey || config?.apiKey || '',
    };
    setSheetsConfig(newConfig);
    setConfig(newConfig);
    setSheetId('');
    setApiKey('');
    toast.success('Sheets configuration saved');
  };

  const handleRemove = () => {
    const token = localStorage.getItem('auth_token');
    let key = 'sheets_config';
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        key = `sheets_config_${payload.email}`;
      } catch {}
    }
    localStorage.removeItem(key);
    setConfig(null);
    toast.success('Sheets configuration removed');
  };

  return (
    <div className="space-y-4 pt-2">
      {config && (
        <div className="rounded-lg border border-border p-3 bg-muted/30 space-y-1">
          <p className="text-xs font-medium text-muted-foreground">Current Configuration</p>
          <p className="text-sm truncate">📋 Sheet ID: <span className="font-mono">{config.sheetId.slice(0, 20)}...</span></p>
          <p className="text-sm">🔑 API Key: <span className="font-mono">••••••••</span></p>
          <Button variant="destructive" size="sm" className="w-full mt-2" onClick={handleRemove}>
            <Trash2 className="h-3 w-3 mr-1" />Remove Configuration
          </Button>
        </div>
      )}
      <div className="space-y-1">
        <Label>Sheet ID</Label>
        <Input value={sheetId} onChange={e => setSheetId(e.target.value)} placeholder="Paste new Sheet ID here" />
      </div>
      <div className="space-y-1">
        <Label>API Key</Label>
        <Input value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="Paste new API Key here" />
      </div>
      <Button onClick={handleSave} className="w-full" disabled={!sheetId && !apiKey}>
        Save Configuration
      </Button>
    </div>
  );
}

export default function Leads() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [budgetFilter, setBudgetFilter] = useState('all');
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [editingLead, setEditingLead] = useState<Lead | null>(null);
  const [editForm, setEditForm] = useState<LeadUpdate>({});
  const [isSaving, setIsSaving] = useState(false);

  const fetchLeads = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.crm.getLeads();
      setLeads(data);
    } catch (err: any) {
      const message = err instanceof ApiError ? err.message : err.message || 'Failed to load leads';
      setError(typeof message === 'string' ? message : JSON.stringify(message));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchLeads(); }, [fetchLeads]);

  const filteredLeads = useMemo(() => {
    return leads.filter(l => {
      if (search) {
        const q = search.toLowerCase();
        if (!(l.name || '').toLowerCase().includes(q) && !(l.phone || '').includes(q) && !(l.email || '').toLowerCase().includes(q) && !(l.city || '').toLowerCase().includes(q)) return false;
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
      followUpToday: leads.filter(l => l.follow_up_due?.startsWith(today)).length,
    };
  }, [leads]);

  const handleEdit = (lead: Lead) => {
    setEditingLead(lead);
    setEditForm({
      name: lead.name || '',
      phone: lead.phone || '',
      email: lead.email || '',
      city: lead.city || '',
      interest: lead.interest || '',
      lead_status: lead.lead_status || 'active',
      lead_score: lead.lead_score,
      budget_category: lead.budget_category || '',
      follow_up_due: lead.follow_up_due || '',
      notes: lead.notes || '',
      agent_handover: lead.agent_handover || 'No',
    });
  };

  const handleSave = async () => {
    if (!editingLead) return;
    setIsSaving(true);
    try {
      const updated = await api.crm.updateLead(editingLead.id, editForm);
      setLeads(leads.map(l => l.id === updated.id ? updated : l));
      setEditingLead(null);
      toast.success('Lead updated');
    } catch (err) {
      toast.error('Failed to update lead');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.crm.deleteLead(id);
      setLeads(leads.filter(l => l.id !== id));
      toast.success('Lead deleted');
    } catch (err) {
      toast.error('Failed to delete lead');
    }
  };

  const exportToCSV = () => {
    const headers = ['Created', 'Name', 'Country Code', 'Phone', 'Interest', 'Email', 'City', 'Last Updated', 'Lead Score', 'Lead Status', 'Follow-Up Due', 'Lead Summary', 'Budget Category', 'Agent Handover', 'Conversation Status', 'Fingerprint'];
    const rows = filteredLeads.map(l => [
      l.created_at || '',
      l.name || '',
      l.country_code || '',
      l.phone || '',
      l.interest || '',
      l.email || '',
      l.city || '',
      l.last_updated || '',
      l.lead_score,
      l.lead_status || '',
      l.follow_up_due || '',
      l.lead_summary || '',
      l.budget_category || '',
      l.agent_handover || '',
      l.conversation_status || '',
      l.user_fingerprint || '',
    ]);
    const csv = [headers, ...rows].map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'leads.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  const uniqueStatuses = useMemo(() => [...new Set(leads.map(l => l.lead_status).filter(Boolean))], [leads]);
  const uniqueBudgets = useMemo(() => [...new Set(leads.map(l => l.budget_category).filter(Boolean))], [leads]);

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
            <Button variant="outline" size="sm" onClick={exportToCSV}><Download className="h-4 w-4 mr-1" />Export CSV</Button>
            <Button variant="outline" size="sm" onClick={fetchLeads} disabled={isLoading}><RefreshCw className={`h-4 w-4 mr-1 ${isLoading ? 'animate-spin' : ''}`} />Refresh</Button>
            <Dialog>
              <DialogTrigger asChild>
                <Button variant="outline" size="sm"><Settings className="h-4 w-4 mr-1" />Sheets Config</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader><DialogTitle>Google Sheets Configuration</DialogTitle></DialogHeader>
                <SheetsConfigForm />
              </DialogContent>
            </Dialog>
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
                       <TableRow key={lead.id} className="hover:bg-primary/5 transition-colors">
                      <TableCell className="text-muted-foreground text-xs">{i + 1}</TableCell>
                      <TableCell className="font-medium text-sm">{lead.name}</TableCell>
                      <TableCell className="text-sm font-mono">{lead.country_code || ''}{lead.phone || ''}</TableCell>
                      <TableCell className="text-sm max-w-[150px] truncate">{lead.interest}</TableCell>
                      <TableCell className="text-sm">{lead.city}</TableCell>
                      <TableCell><LeadScoreBadge score={lead.lead_score} /></TableCell>
                      <TableCell><LeadStatusBadge status={lead.lead_status} /></TableCell>
                      <TableCell className="text-sm">{lead.follow_up_due || '—'}</TableCell>
                      <TableCell className="text-sm">{lead.budget_category || '—'}</TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="icon" onClick={() => setSelectedLead(lead)} title="View"><Eye className="h-3 w-3" /></Button>
                          <Button variant="ghost" size="icon" onClick={() => { navigator.clipboard.writeText(`${lead.country_code || ''}${lead.phone || ''}`); toast.success('Phone copied'); }} title="Copy phone"><Copy className="h-3 w-3" /></Button>
                          <Dialog open={editingLead?.id === lead.id} onOpenChange={(open) => !open && setEditingLead(null)}>
                            <DialogTrigger asChild>
                              <Button variant="ghost" size="icon" onClick={() => handleEdit(lead)}><Edit className="h-3 w-3" /></Button>
                            </DialogTrigger>
                            <DialogContent className="max-w-lg">
                              <DialogHeader><DialogTitle>Edit Lead — {editingLead?.name}</DialogTitle></DialogHeader>
                              <div className="grid gap-4 py-4 sm:grid-cols-2">
                                {[
                                  { key: 'name', label: 'Name' },
                                  { key: 'phone', label: 'Phone' },
                                  { key: 'email', label: 'Email' },
                                  { key: 'city', label: 'City' },
                                  { key: 'interest', label: 'Interest' },
                                  { key: 'budget_category', label: 'Budget' },
                                  { key: 'follow_up_due', label: 'Follow-up Due' },
                                  { key: 'lead_score', label: 'Score', type: 'number' },
                                ].map(({ key, label, type }) => (
                                  <div key={key} className="space-y-1">
                                    <Label>{label}</Label>
                                    <Input
                                      type={type || 'text'}
                                      value={(editForm as any)[key] ?? ''}
                                      onChange={e => setEditForm(prev => ({ ...prev, [key]: type === 'number' ? Number(e.target.value) : e.target.value }))}
                                    />
                                  </div>
                                ))}
                                <div className="space-y-1">
                                  <Label>Status</Label>
                                  <Select value={editForm.lead_status || 'active'} onValueChange={v => setEditForm(prev => ({ ...prev, lead_status: v }))}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                      <SelectItem value="active">Active</SelectItem>
                                      <SelectItem value="converted">Converted</SelectItem>
                                      <SelectItem value="lost">Lost</SelectItem>
                                    </SelectContent>
                                  </Select>
                                </div>
                                <div className="space-y-1">
                                  <Label>Agent Handover</Label>
                                  <Select value={editForm.agent_handover || 'No'} onValueChange={v => setEditForm(prev => ({ ...prev, agent_handover: v }))}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                      <SelectItem value="No">No</SelectItem>
                                      <SelectItem value="Yes">Yes</SelectItem>
                                    </SelectContent>
                                  </Select>
                                </div>
                                <div className="space-y-1 sm:col-span-2">
                                  <Label>Notes</Label>
                                  <Input value={editForm.notes ?? ''} onChange={e => setEditForm(prev => ({ ...prev, notes: e.target.value }))} placeholder="Add notes..." />
                                </div>
                              </div>
                              <div className="flex justify-end gap-2">
                                <Button variant="outline" onClick={() => setEditingLead(null)}>Cancel</Button>
                                <Button onClick={handleSave} disabled={isSaving}>
                                  {isSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}Save
                                </Button>
                              </div>
                            </DialogContent>
                          </Dialog>
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive"><Trash2 className="h-3 w-3" /></Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Delete Lead?</AlertDialogTitle>
                                <AlertDialogDescription>This will permanently delete {lead.name}'s data.</AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Cancel</AlertDialogCancel>
                                <AlertDialogAction onClick={() => handleDelete(lead.id)}>Delete</AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
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
                    ['Phone', `${selectedLead.country_code || ''}${selectedLead.phone || ''}`],
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
                    const headers = ['Created', 'Name', 'Country Code', 'Phone', 'Interest', 'Email', 'City', 'Last Updated', 'Lead Score', 'Lead Status', 'Follow-Up Due', 'Lead Summary', 'Budget Category', 'Agent Handover', 'Conversation Status', 'Fingerprint'];
                        const values = [
                          selectedLead.created_at || '',
                          selectedLead.name || '',
                          selectedLead.country_code || '',
                          selectedLead.phone || '',
                          selectedLead.interest || '',
                          selectedLead.email || '',
                          selectedLead.city || '',
                          selectedLead.last_updated || '',
                          selectedLead.lead_score,
                          selectedLead.lead_status || '',
                          selectedLead.follow_up_due || '',
                          selectedLead.lead_summary || '',
                          selectedLead.budget_category || '',
                          selectedLead.agent_handover || '',
                          selectedLead.conversation_status || '',
                          selectedLead.user_fingerprint || '',
                      new Date(selectedLead.created_at).toLocaleDateString(),
                    ];
                    const csv = [headers.join(','), values.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')].join('\n');
                    const blob = new Blob([csv], { type: 'text/csv' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url; a.download = `lead_${selectedLead.name}.csv`; a.click();
                    toast.success('Lead exported');
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
