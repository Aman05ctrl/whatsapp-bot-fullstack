import { useEffect, useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { api, Property, ApiError } from '@/lib/api';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import {
  Building2, TrendingUp, CheckCircle2, DollarSign, Plus, AlertCircle, Home, Eye,
} from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts';
import {
  getMonthlyData, getPropertyTypeStats, getSoldInPeriod, formatCurrency,
} from '@/services/analytics.service';

function AnimatedCounter({ value, prefix = '' }: { value: number; prefix?: string }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    const duration = 800;
    const steps = 30;
    const increment = value / steps;
    let current = 0;
    const timer = setInterval(() => {
      current += increment;
      if (current >= value) {
        setDisplay(value);
        clearInterval(timer);
      } else {
        setDisplay(Math.floor(current));
      }
    }, duration / steps);
    return () => clearInterval(timer);
  }, [value]);
  return <>{prefix}{display.toLocaleString()}</>;
}

export default function Dashboard() {
  const [properties, setProperties] = useState<Property[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchProperties = async () => {
      try {
        const response = await api.properties.list({ size: 100 });
        setProperties(response.items || []);
      } catch (err) {
        const message = err instanceof ApiError ? err.message : 'Failed to load properties';
        setError(message);
      } finally {
        setIsLoading(false);
      }
    };
    fetchProperties();
  }, []);

  const active = useMemo(() => properties.filter(p => !p.is_deleted), [properties]);
  const sold = useMemo(() => active.filter(p => p.is_sold), [active]);
  const available = useMemo(() => active.filter(p => !p.is_sold), [active]);

  const stats = useMemo(() => ({
    total: active.length,
    available: available.length,
    sold: sold.length,
    totalValue: active.reduce((s, p) => s + (p.price || 0), 0),
    avgPrice: active.length ? active.reduce((s, p) => s + (p.price || 0), 0) / active.length : 0,
    soldRevenue: sold.reduce((s, p) => s + (p.price || 0), 0),
  }), [active, sold, available]);

  const monthlyData = useMemo(() => getMonthlyData(properties), [properties]);
  const typeData = useMemo(() => getPropertyTypeStats(properties), [properties]);

  const recentProperties = useMemo(() =>
    active.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 6),
    [active]
  );

  const topPerformer = useMemo(() =>
    sold.sort((a, b) => (b.price || 0) - (a.price || 0))[0],
    [sold]
  );

  const periodBreakdown = [
    { label: '1 Day', days: 1 },
    { label: '1 Week', days: 7 },
    { label: '15 Days', days: 15 },
    { label: '1 Month', days: 30 },
    { label: '6 Months', days: 180 },
    { label: '1 Year', days: 365 },
  ];

  const periodCounts = useMemo(() =>
    periodBreakdown.map(p => ({ ...p, count: getSoldInPeriod(properties, p.days) })),
    [properties]
  );

  const maxPeriod = useMemo(() =>
    periodCounts.reduce((max, p) => p.count > max.count ? p : max, periodCounts[0]),
    [periodCounts]
  );

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="space-y-6 animate-fade-in">
          <Skeleton className="h-8 w-48" />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-32 rounded-xl" />)}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Skeleton className="h-72 rounded-xl" />
            <Skeleton className="h-72 rounded-xl" />
          </div>
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
            <h1 className="page-header text-3xl">Dashboard</h1>
            <p className="text-muted-foreground text-sm mt-1">Welcome back! Here's your property overview.</p>
          </div>
          <Link to="/properties/new">
            <Button className="gap-2"><Plus className="h-4 w-4" />Add Property</Button>
          </Link>
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* SECTION 1: Hero Stats */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { title: 'Total Properties', value: stats.total, icon: Building2, color: 'text-primary', prefix: '' },
            { title: 'Available', value: stats.available, icon: TrendingUp, color: 'text-success', prefix: '' },
            { title: 'Sold', value: stats.sold, icon: CheckCircle2, color: 'text-accent', prefix: '' },
            { title: 'Portfolio Value', value: stats.totalValue, icon: DollarSign, color: 'text-primary', prefix: '$', formatted: formatCurrency(stats.totalValue) },
          ].map((stat, i) => (
            <Card key={i} className="card-elevated glow-border overflow-hidden">
              <CardContent className="p-5">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{stat.title}</p>
                  <stat.icon className={`h-5 w-5 ${stat.color}`} />
                </div>
                <p className={`text-3xl font-bold ${stat.color}`}>
                  {stat.formatted || <AnimatedCounter value={stat.value} prefix={stat.prefix} />}
                </p>
                {stat.title === 'Available' && stats.total > 0 && (
                  <p className="text-xs text-muted-foreground mt-1">{((stats.available / stats.total) * 100).toFixed(0)}% of total</p>
                )}
                {stat.title === 'Sold' && (
                  <p className="text-xs text-muted-foreground mt-1">Revenue: {formatCurrency(stats.soldRevenue)}</p>
                )}
                {stat.title === 'Portfolio Value' && (
                  <p className="text-xs text-muted-foreground mt-1">Avg: {formatCurrency(stats.avgPrice)}/property</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>

        {/* SECTION 2: Charts */}
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="card-elevated glow-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Sales Timeline</CardTitle>
            </CardHeader>
            <CardContent className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={monthlyData}>
                  <defs>
                    <linearGradient id="salesGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="month" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                  <YAxis tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      background: 'hsl(var(--card))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                      color: 'hsl(var(--foreground))',
                    }}
                    formatter={(value: number) => [`${value} properties sold`, 'Sales']}
                  />
                  <Area
                    type="monotone"
                    dataKey="sold"
                    stroke="hsl(var(--primary))"
                    fill="url(#salesGradient)"
                    strokeWidth={2}
                    animationDuration={1200}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card className="card-elevated glow-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Property Type Distribution</CardTitle>
            </CardHeader>
            <CardContent className="h-64">
              {typeData.length === 0 ? (
                <div className="flex items-center justify-center h-full text-muted-foreground text-sm">No data</div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={typeData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={3} dataKey="value" animationDuration={1000}>
                      {typeData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px', color: 'hsl(var(--foreground))' }} />
                    <Legend formatter={(value) => <span className="text-xs text-foreground">{value}</span>} />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </div>

        {/* SECTION 3: Performance */}
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="card-elevated glow-border">
            <CardHeader className="pb-2"><CardTitle className="text-base">Top Performer</CardTitle></CardHeader>
            <CardContent>
              {topPerformer ? (
                <div className="flex items-center gap-4">
                  <div className="h-16 w-16 rounded-lg bg-muted flex items-center justify-center overflow-hidden shrink-0">
                    {topPerformer.primary_image_url ? (
                      <img src={topPerformer.primary_image_url} alt="" className="h-full w-full object-cover" />
                    ) : (
                      <Home className="h-8 w-8 text-muted-foreground" />
                    )}
                  </div>
                  <div className="min-w-0">
                    <p className="font-semibold truncate">{topPerformer.title}</p>
                    <p className="text-sm text-muted-foreground">{topPerformer.city}</p>
                    <p className="text-lg font-bold text-primary mt-1">{formatCurrency(topPerformer.price || 0)}</p>
                  </div>
                  <span className="ml-auto text-lg">💰</span>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground py-4 text-center">No sold properties yet</p>
              )}
            </CardContent>
          </Card>

          <Card className="card-elevated glow-border">
            <CardHeader className="pb-2"><CardTitle className="text-base">Recent Activity</CardTitle></CardHeader>
            <CardContent>
              {active.slice(0, 5).map((p, i) => (
                <div key={p.id} className="flex items-center gap-3 py-2 border-b border-border last:border-0">
                  <div className={`h-2 w-2 rounded-full ${p.is_sold ? 'bg-success' : 'bg-primary'}`} />
                  <p className="text-sm truncate flex-1">{p.title}</p>
                  <span className={p.is_sold ? 'status-sold' : 'status-available'}>
                    {p.is_sold ? 'Sold' : 'Active'}
                  </span>
                </div>
              ))}
              {active.length === 0 && <p className="text-sm text-muted-foreground text-center py-4">No activity</p>}
            </CardContent>
          </Card>
        </div>

        {/* SECTION 4: Sales Period Breakdown */}
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
          {periodCounts.map((p) => (
            <Card
              key={p.label}
              className={`card-elevated text-center py-4 ${p.label === maxPeriod.label ? 'ring-2 ring-primary' : 'glow-border'}`}
            >
              <p className="text-2xl font-bold text-primary">{p.count}</p>
              <p className="text-[10px] text-muted-foreground mt-1">{p.label}</p>
            </Card>
          ))}
        </div>

        {/* SECTION 5: Monthly Heatmap */}
        <Card className="card-elevated glow-border">
          <CardHeader className="pb-2"><CardTitle className="text-base">Monthly Sales Heatmap</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-6 sm:grid-cols-12 gap-2">
              {monthlyData.map((m) => {
                const intensity = m.sold > 0 ? Math.min(m.sold / 5, 1) : 0;
                return (
                  <div
                    key={m.month}
                    className="aspect-square rounded-lg flex flex-col items-center justify-center text-xs cursor-default transition-transform hover:scale-105"
                    style={{
                      background: m.sold > 0
                        ? `hsl(142 71% 45% / ${0.15 + intensity * 0.6})`
                        : 'hsl(var(--muted))',
                    }}
                    title={`${m.sold} sold in ${m.month}`}
                  >
                    <span className="font-bold">{m.sold}</span>
                    <span className="text-[9px] text-muted-foreground">{m.month}</span>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* SECTION 6: Recent Properties Table */}
        <Card className="card-elevated glow-border">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-base">Recent Properties</CardTitle>
            <Link to="/properties">
              <Button variant="ghost" size="sm">View All</Button>
            </Link>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Property</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>City</TableHead>
                  <TableHead>Price</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentProperties.map((p) => (
                  <TableRow key={p.id} className="hover:bg-primary/5 transition-colors">
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <div className="h-9 w-9 rounded-lg bg-muted flex items-center justify-center overflow-hidden shrink-0">
                          {p.primary_image_url ? (
                            <img src={p.primary_image_url} alt="" className="h-full w-full object-cover" />
                          ) : (
                            <Home className="h-4 w-4 text-muted-foreground" />
                          )}
                        </div>
                        <span className="font-medium text-sm truncate">{p.title}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">{p.property_type || '—'}</TableCell>
                    <TableCell className="text-sm">{p.city || '—'}</TableCell>
                    <TableCell className="text-sm font-medium">{p.price ? formatCurrency(p.price) : '—'}</TableCell>
                    <TableCell>
                      <span className={p.is_sold ? 'status-sold' : p.is_deleted ? 'status-inactive' : 'status-available'}>
                        {p.is_sold ? 'Sold' : p.is_deleted ? 'Inactive' : 'Available'}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      <Link to={`/properties/${p.id}`}>
                        <Button variant="ghost" size="icon"><Eye className="h-4 w-4" /></Button>
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
