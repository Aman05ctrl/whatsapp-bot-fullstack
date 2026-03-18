import { useEffect, useState, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { api, Property, ApiError } from '@/lib/api';
import {
  Plus, Search, Home, Grid, List, AlertCircle, ChevronLeft, ChevronRight, Eye, Edit,
} from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

type ViewMode = 'table' | 'cards';

export default function Properties() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [properties, setProperties] = useState<Property[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [totalPages, setTotalPages] = useState(1);

  const currentPage = parseInt(searchParams.get('page') || '1');
  const searchQuery = searchParams.get('search') || '';
  const statusFilter = searchParams.get('status') || 'all';

  const fetchProperties = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params: Record<string, unknown> = { page: currentPage, size: 10 };
      if (searchQuery) params.search = searchQuery;
      if (statusFilter === 'available') params.is_sold = false;
      else if (statusFilter === 'sold') params.is_sold = true;
      const response = await api.properties.list(params);
      setProperties(response.items || []);
      setTotalPages(response.pages || 1);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to load properties';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [currentPage, searchQuery, statusFilter]);

  useEffect(() => { fetchProperties(); }, [fetchProperties]);

  const updateFilter = (key: string, value: string) => {
    const newParams = new URLSearchParams(searchParams);
    if (value && value !== 'all') newParams.set(key, value);
    else newParams.delete(key);
    if (key !== 'page') newParams.set('page', '1');
    setSearchParams(newParams);
  };

  const handleSearch = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    updateFilter('search', formData.get('search') as string);
  };

  const getPropertyImage = (p: Property) => {
    if (p.primary_image_url) return p.primary_image_url;
    const imgs = p.images as any[];
    if (imgs?.length) {
      const primary = imgs.find((i: any) => i.is_primary);
      return primary?.image_url || primary?.url || imgs[0]?.image_url || imgs[0]?.url;
    }
    return null;
  };

  return (
    <DashboardLayout>
      <div className="space-y-6 animate-fade-in">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="page-header text-3xl">Properties</h1>
            <p className="text-muted-foreground text-sm mt-1">Manage your property listings</p>
          </div>
          <Link to="/properties/new">
            <Button className="gap-2"><Plus className="h-4 w-4" />Add Property</Button>
          </Link>
        </div>

        {/* Filters */}
        <Card className="card-elevated glow-border">
          <CardContent className="p-4">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-1 gap-3">
                <form onSubmit={handleSearch} className="relative flex-1 max-w-sm">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input name="search" placeholder="Search properties..." className="pl-9" defaultValue={searchQuery} />
                </form>
                <Select value={statusFilter} onValueChange={(v) => updateFilter('status', v)}>
                  <SelectTrigger className="w-[140px]"><SelectValue placeholder="Status" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="available">Available</SelectItem>
                    <SelectItem value="sold">Sold</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex gap-1 border border-border rounded-lg p-1">
                <Button variant={viewMode === 'table' ? 'secondary' : 'ghost'} size="icon" onClick={() => setViewMode('table')}><List className="h-4 w-4" /></Button>
                <Button variant={viewMode === 'cards' ? 'secondary' : 'ghost'} size="icon" onClick={() => setViewMode('cards')}><Grid className="h-4 w-4" /></Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {error && <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}

        {isLoading ? (
          <div className="space-y-3">{[1,2,3,4,5].map(i => <Skeleton key={i} className="h-16 rounded-xl" />)}</div>
        ) : properties.length === 0 ? (
          <Card className="card-elevated">
            <CardContent className="flex flex-col items-center justify-center py-16">
              <Home className="h-16 w-16 text-muted-foreground/20 mb-4" />
              <p className="text-muted-foreground mb-4">No properties found</p>
              <Link to="/properties/new"><Button variant="outline"><Plus className="h-4 w-4 mr-2" />Add your first property</Button></Link>
            </CardContent>
          </Card>
        ) : viewMode === 'table' ? (
          <Card className="card-elevated glow-border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Property</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Price</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {properties.map((property) => {
                  const img = getPropertyImage(property);
                  return (
                    <TableRow key={property.id} className="hover:bg-primary/5 transition-all duration-150">
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="h-10 w-10 rounded-lg bg-muted flex items-center justify-center overflow-hidden shrink-0">
                            {img ? <img src={img} alt={property.title} className="h-full w-full object-cover" /> : <Home className="h-5 w-5 text-muted-foreground" />}
                          </div>
                          <div>
                            <p className="font-medium text-sm">{property.title}</p>
                            {(property.bedrooms || property.bathrooms) && (
                              <p className="text-xs text-muted-foreground">
                                {property.bedrooms && `${property.bedrooms} bed`}
                                {property.bedrooms && property.bathrooms && ' • '}
                                {property.bathrooms && `${property.bathrooms} bath`}
                              </p>
                            )}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-sm">{property.property_type || '—'}</TableCell>
                      <TableCell className="text-sm">{property.city && property.state ? `${property.city}, ${property.state}` : property.address || '—'}</TableCell>
                      <TableCell className="text-sm font-medium">{property.price ? `$${property.price.toLocaleString()}` : '—'}</TableCell>
                      <TableCell>
                        <span className={property.is_sold ? 'status-sold' : 'status-available'}>
                          {property.is_sold ? 'Sold' : 'Available'}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Link to={`/properties/${property.id}`}><Button variant="ghost" size="icon"><Eye className="h-4 w-4" /></Button></Link>
                          <Link to={`/properties/${property.id}/edit`}><Button variant="ghost" size="icon"><Edit className="h-4 w-4" /></Button></Link>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {properties.map((property) => {
              const img = getPropertyImage(property);
              return (
                <Link key={property.id} to={`/properties/${property.id}`}>
                  <Card className="card-elevated overflow-hidden group cursor-pointer transition-transform duration-200 hover:scale-[1.02]">
                    <div className="aspect-video bg-muted flex items-center justify-center overflow-hidden">
                      {img ? <img src={img} alt={property.title} className="h-full w-full object-cover group-hover:scale-105 transition-transform duration-300" /> : <Home className="h-12 w-12 text-muted-foreground/20" />}
                    </div>
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <h3 className="font-semibold truncate">{property.title}</h3>
                          <p className="text-sm text-muted-foreground truncate">{property.city && property.state ? `${property.city}, ${property.state}` : property.address || 'No address'}</p>
                        </div>
                        <span className={property.is_sold ? 'status-sold' : 'status-available'}>{property.is_sold ? 'Sold' : 'Available'}</span>
                      </div>
                      <p className="mt-2 text-lg font-bold text-primary">{property.price ? `$${property.price.toLocaleString()}` : 'Price TBD'}</p>
                      <div className="mt-2 flex gap-3 text-sm text-muted-foreground">
                        {property.bedrooms && <span>{property.bedrooms} bed</span>}
                        {property.bathrooms && <span>{property.bathrooms} bath</span>}
                        {property.area_sqft && <span>{property.area_sqft.toLocaleString()} sqft</span>}
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {!isLoading && properties.length > 0 && totalPages > 1 && (
          <div className="flex items-center justify-center gap-2">
            <Button variant="outline" size="icon" disabled={currentPage <= 1} onClick={() => updateFilter('page', String(currentPage - 1))}><ChevronLeft className="h-4 w-4" /></Button>
            <span className="text-sm text-muted-foreground">Page {currentPage} of {totalPages}</span>
            <Button variant="outline" size="icon" disabled={currentPage >= totalPages} onClick={() => updateFilter('page', String(currentPage + 1))}><ChevronRight className="h-4 w-4" /></Button>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
