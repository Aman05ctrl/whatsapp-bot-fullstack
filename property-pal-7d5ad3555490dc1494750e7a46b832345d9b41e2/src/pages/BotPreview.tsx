import { useState } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { api, Property, ApiError } from '@/lib/api';
import {
  Search, Loader2, AlertCircle, Home, MapPin, Bed, Bath, Maximize, MessageCircle,
} from 'lucide-react';

export default function BotPreview() {
  const [results, setResults] = useState<Property[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [filters, setFilters] = useState<Record<string, string>>({});

  const handleFilterChange = (key: string, value: string) => {
    setFilters((prev) => {
      const next = { ...prev };
      if (value && value !== 'any') next[key] = value;
      else delete next[key];
      return next;
    });
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setHasSearched(true);
    try {
      const params: Record<string, unknown> = {};
      Object.entries(filters).forEach(([key, value]) => {
        if (value && value !== 'any') params[key] = value;
      });
      const data = await api.bot.search(params);
      setResults(data);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Search failed';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClear = () => {
    setFilters({});
    setResults([]);
    setHasSearched(false);
    setError(null);
  };

  return (
    <DashboardLayout>
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="page-header text-3xl flex items-center gap-2">
            <MessageCircle className="h-7 w-7" />
            Bot Preview
          </h1>
          <p className="text-muted-foreground text-sm mt-1">Preview how properties appear in WhatsApp bot search</p>
        </div>

        {/* Search Form */}
        <Card className="card-elevated glow-border">
          <CardHeader><CardTitle className="text-base">Search Properties</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={handleSearch} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div className="space-y-2"><Label>City</Label><Input value={filters.city || ''} onChange={(e) => handleFilterChange('city', e.target.value)} placeholder="e.g., Los Angeles" /></div>
                <div className="space-y-2"><Label>Property Type</Label>
                  <Select value={filters.property_type || 'any'} onValueChange={(v) => handleFilterChange('property_type', v)}>
                    <SelectTrigger><SelectValue placeholder="Any type" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="any">Any type</SelectItem>
                      <SelectItem value="House">House</SelectItem>
                      <SelectItem value="Apartment">Apartment</SelectItem>
                      <SelectItem value="Condo">Condo</SelectItem>
                      <SelectItem value="Townhouse">Townhouse</SelectItem>
                      <SelectItem value="Land">Land</SelectItem>
                      <SelectItem value="Commercial">Commercial</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2"><Label>Min Price</Label><Input type="number" min={0} value={filters.min_price || ''} onChange={(e) => handleFilterChange('min_price', e.target.value)} placeholder="100000" /></div>
                <div className="space-y-2"><Label>Max Price</Label><Input type="number" min={0} value={filters.max_price || ''} onChange={(e) => handleFilterChange('max_price', e.target.value)} placeholder="500000" /></div>
                <div className="space-y-2"><Label>Min Bedrooms</Label>
                  <Select value={filters.bedrooms || 'any'} onValueChange={(v) => handleFilterChange('bedrooms', v)}>
                    <SelectTrigger><SelectValue placeholder="Any" /></SelectTrigger>
                    <SelectContent><SelectItem value="any">Any</SelectItem>{[1,2,3,4,5].map(n => <SelectItem key={n} value={String(n)}>{n}+</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div className="space-y-2"><Label>Min Bathrooms</Label>
                  <Select value={filters.bathrooms || 'any'} onValueChange={(v) => handleFilterChange('bathrooms', v)}>
                    <SelectTrigger><SelectValue placeholder="Any" /></SelectTrigger>
                    <SelectContent><SelectItem value="any">Any</SelectItem>{[1,2,3,4].map(n => <SelectItem key={n} value={String(n)}>{n}+</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex gap-2 pt-2">
                <Button type="submit" disabled={isLoading}>{isLoading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Search className="h-4 w-4 mr-2" />}Search</Button>
                <Button type="button" variant="outline" onClick={handleClear}>Clear</Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {error && <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}

        {/* Results - Phone Mockup */}
        {hasSearched && (
          <div className="flex justify-center">
            <div className="w-[380px] rounded-[2.5rem] border-4 border-muted p-2 shadow-2xl" style={{ background: 'hsl(var(--card))' }}>
              {/* Phone notch */}
              <div className="flex justify-center mb-2">
                <div className="w-24 h-5 bg-muted rounded-full" />
              </div>
              {/* WhatsApp header */}
              <div className="rounded-t-xl px-4 py-3 flex items-center gap-3" style={{ background: 'hsl(var(--primary) / 0.15)' }}>
                <div className="h-8 w-8 rounded-full bg-primary/30 flex items-center justify-center"><MessageCircle className="h-4 w-4 text-primary" /></div>
                <div>
                  <p className="text-sm font-semibold">Property Bot</p>
                  <p className="text-[10px] text-muted-foreground">Online</p>
                </div>
              </div>
              {/* Chat area */}
              <div className="p-3 space-y-3 max-h-[500px] overflow-y-auto min-h-[300px]" style={{ background: 'hsl(var(--background) / 0.5)' }}>
                {results.length === 0 ? (
                  <div className="text-center py-12">
                    <Home className="h-10 w-10 text-muted-foreground/20 mx-auto mb-2" />
                    <p className="text-sm text-muted-foreground">No properties found</p>
                  </div>
                ) : (
                  <>
                    <div className="ml-auto max-w-[80%] rounded-xl rounded-tr-none px-3 py-2 text-sm" style={{ background: 'hsl(var(--primary) / 0.15)' }}>
                      🏠 Found {results.length} {results.length === 1 ? 'property' : 'properties'}!
                    </div>
                    {results.map((property) => (
                      <div key={property.id} className="max-w-[85%] rounded-xl overflow-hidden border border-border" style={{ background: 'hsl(var(--card))' }}>
                        <div className="aspect-video bg-muted flex items-center justify-center overflow-hidden">
                          {property.primary_image_url ? <img src={property.primary_image_url} alt={property.title} className="h-full w-full object-cover" /> : <Home className="h-8 w-8 text-muted-foreground/20" />}
                        </div>
                        <div className="p-2.5 space-y-1.5">
                          <h3 className="font-semibold text-sm">{property.title}</h3>
                          {(property.city || property.state) && (
                            <div className="flex items-center gap-1 text-xs text-muted-foreground"><MapPin className="h-3 w-3" />{property.city}{property.city && property.state && ', '}{property.state}</div>
                          )}
                          <p className="text-base font-bold text-primary">{property.price ? `$${property.price.toLocaleString()}` : 'Price on request'}</p>
                          <div className="flex gap-3 text-xs text-muted-foreground">
                            {property.bedrooms !== undefined && <span className="flex items-center gap-1"><Bed className="h-3 w-3" />{property.bedrooms}</span>}
                            {property.bathrooms !== undefined && <span className="flex items-center gap-1"><Bath className="h-3 w-3" />{property.bathrooms}</span>}
                            {property.area_sqft !== undefined && <span className="flex items-center gap-1"><Maximize className="h-3 w-3" />{property.area_sqft.toLocaleString()}</span>}
                          </div>
                          <span className={property.is_sold ? 'status-sold' : 'status-available'}>{property.is_sold ? 'Sold' : 'Available'}</span>
                        </div>
                      </div>
                    ))}
                    <div className="ml-auto max-w-[80%] rounded-xl rounded-tr-none px-3 py-2 text-sm" style={{ background: 'hsl(var(--primary) / 0.15)' }}>
                      💬 Reply with a number for details!
                    </div>
                  </>
                )}
              </div>
              {/* Bottom bar */}
              <div className="rounded-b-xl px-3 py-2 border-t border-border flex items-center gap-2">
                <div className="flex-1 h-8 rounded-full bg-muted" />
                <div className="h-8 w-8 rounded-full bg-primary/30 flex items-center justify-center"><Search className="h-3 w-3 text-primary" /></div>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
