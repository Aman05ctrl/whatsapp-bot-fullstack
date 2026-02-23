import { useEffect, useState, useMemo } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { api, Property, ApiError } from '@/lib/api';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  AlertCircle, DollarSign, TrendingUp, MapPin, Home, BarChart3,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { getMonthlyData, getPropertyTypeStats, formatCurrency } from '@/services/analytics.service';

export default function Analytics() {
  const [properties, setProperties] = useState<Property[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.properties.list({ size: 1000 });
        setProperties(res.items || []);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'Failed to load');
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  const active = useMemo(() => properties.filter(p => !p.is_deleted), [properties]);
  const sold = useMemo(() => active.filter(p => p.is_sold), [active]);
  const monthlyData = useMemo(() => getMonthlyData(properties), [properties]);
  const typeData = useMemo(() => getPropertyTypeStats(properties), [properties]);

  const kpis = useMemo(() => {
    const totalRevenue = sold.reduce((s, p) => s + (p.price || 0), 0);
    const avgSalePrice = sold.length ? totalRevenue / sold.length : 0;
    const conversionRate = active.length ? ((sold.length / active.length) * 100).toFixed(1) : '0';
    const cityCount: Record<string, number> = {};
    active.forEach(p => { if (p.city) cityCount[p.city] = (cityCount[p.city] || 0) + 1; });
    const topCity = Object.entries(cityCount).sort(([, a], [, b]) => b - a)[0]?.[0] || 'N/A';
    const typeCount: Record<string, number> = {};
    active.forEach(p => { const t = p.property_type || 'Other'; typeCount[t] = (typeCount[t] || 0) + 1; });
    const topType = Object.entries(typeCount).sort(([, a], [, b]) => b - a)[0]?.[0] || 'N/A';
    return { totalRevenue, avgSalePrice, conversionRate, topCity, topType };
  }, [active, sold]);

  const topSold = useMemo(() => [...sold].sort((a, b) => (b.price || 0) - (a.price || 0)), [sold]);
  const bestMonth = useMemo(() => monthlyData.reduce((m, d) => d.sold > m.sold ? d : m, monthlyData[0]), [monthlyData]);

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="space-y-6">
          <Skeleton className="h-8 w-56" />
          <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
            {[1,2,3,4,5,6].map(i => <Skeleton key={i} className="h-24 rounded-xl" />)}
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="page-header text-3xl">Analytics & Insights</h1>
          <p className="text-muted-foreground text-sm mt-1">Deep dive into your property portfolio performance</p>
        </div>

        {error && <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}

        {/* KPIs */}
        <div className="grid gap-3 grid-cols-2 lg:grid-cols-6">
          {[
            { label: 'Total Revenue', value: formatCurrency(kpis.totalRevenue), icon: DollarSign },
            { label: 'Avg Sale Price', value: formatCurrency(kpis.avgSalePrice), icon: TrendingUp },
            { label: 'Conversion Rate', value: `${kpis.conversionRate}%`, icon: BarChart3 },
            { label: 'Top City', value: kpis.topCity, icon: MapPin },
            { label: 'Top Type', value: kpis.topType, icon: Home },
            { label: 'Avg Days to Sell', value: 'N/A', icon: TrendingUp },
          ].map((kpi, i) => (
            <Card key={i} className="card-elevated glow-border">
              <CardContent className="p-4">
                <kpi.icon className="h-4 w-4 text-primary mb-2" />
                <p className="text-lg font-bold truncate">{kpi.value}</p>
                <p className="text-[10px] text-muted-foreground">{kpi.label}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Revenue Chart */}
        <Card className="card-elevated glow-border">
          <CardHeader className="pb-2"><CardTitle className="text-base">Monthly Revenue</CardTitle></CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={monthlyData}>
                <XAxis dataKey="month" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                <YAxis tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" tickFormatter={(v) => `$${(v/1000).toFixed(0)}K`} />
                <Tooltip
                  contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px', color: 'hsl(var(--foreground))' }}
                  formatter={(v: number) => [formatCurrency(v), 'Revenue']}
                />
                <Bar dataKey="revenue" radius={[6, 6, 0, 0]} animationDuration={1000}>
                  {monthlyData.map((_, i) => (
                    <Cell key={i} fill="hsl(var(--primary))" fillOpacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Two Columns */}
        <div className="grid gap-4 lg:grid-cols-2">
          {/* Best/Worst Performers */}
          <Card className="card-elevated glow-border">
            <CardHeader className="pb-2"><CardTitle className="text-base">Best & Worst Performers</CardTitle></CardHeader>
            <CardContent>
              {sold.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">No sold properties to analyze</p>
              ) : (
                <div className="space-y-4">
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-2">🏆 Top 3</p>
                    {topSold.slice(0, 3).map((p, i) => (
                      <div key={p.id} className="flex items-center gap-3 py-2 border-b border-border last:border-0">
                        <span className="text-lg">{['🥇', '🥈', '🥉'][i]}</span>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{p.title}</p>
                          <p className="text-xs text-muted-foreground">{p.city}</p>
                        </div>
                        <span className="font-semibold text-sm text-primary">{formatCurrency(p.price || 0)}</span>
                      </div>
                    ))}
                  </div>
                  {topSold.length > 3 && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-2">📉 Bottom 3</p>
                      {topSold.slice(-3).reverse().map((p) => (
                        <div key={p.id} className="flex items-center gap-3 py-2 border-b border-border last:border-0">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">{p.title}</p>
                            <p className="text-xs text-muted-foreground">{p.city}</p>
                          </div>
                          <span className="font-semibold text-sm">{formatCurrency(p.price || 0)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Property Type Analysis */}
          <Card className="card-elevated glow-border">
            <CardHeader className="pb-2"><CardTitle className="text-base">Property Type Analysis</CardTitle></CardHeader>
            <CardContent className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={typeData} layout="vertical">
                  <XAxis type="number" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                  <YAxis dataKey="name" type="category" width={80} tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                  <Tooltip contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px', color: 'hsl(var(--foreground))' }} />
                  <Bar dataKey="value" radius={[0, 6, 6, 0]} animationDuration={1000}>
                    {typeData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>

        {/* Monthly Sales Table */}
        <Card className="card-elevated glow-border">
          <CardHeader className="pb-2"><CardTitle className="text-base">Monthly Sales Breakdown</CardTitle></CardHeader>
          <CardContent className="p-0 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left p-3 text-muted-foreground font-medium">Month</th>
                  <th className="text-right p-3 text-muted-foreground font-medium">Sold</th>
                  <th className="text-right p-3 text-muted-foreground font-medium">Revenue</th>
                  <th className="text-right p-3 text-muted-foreground font-medium">Avg Price</th>
                </tr>
              </thead>
              <tbody>
                {monthlyData.map((m, i) => (
                  <tr
                    key={m.month}
                    className={`border-b border-border transition-colors ${
                      m.sold === 0 ? 'bg-destructive/5' : m.month === bestMonth.month ? 'bg-success/10' : 'hover:bg-primary/5'
                    }`}
                  >
                    <td className="p-3 font-medium">{m.month}</td>
                    <td className="p-3 text-right">{m.sold}</td>
                    <td className="p-3 text-right">{formatCurrency(m.revenue)}</td>
                    <td className="p-3 text-right">{m.sold > 0 ? formatCurrency(m.revenue / m.sold) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
