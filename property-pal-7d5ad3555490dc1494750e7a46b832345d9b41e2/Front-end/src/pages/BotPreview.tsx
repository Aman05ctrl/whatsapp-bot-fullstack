 import { useState } from 'react';
 import { DashboardLayout } from '@/components/layout/DashboardLayout';
 import { Button } from '@/components/ui/button';
 import { Input } from '@/components/ui/input';
 import { Label } from '@/components/ui/label';
 import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
 import { Alert, AlertDescription } from '@/components/ui/alert';
 import {
   Select,
   SelectContent,
   SelectItem,
   SelectTrigger,
   SelectValue,
 } from '@/components/ui/select';
 import { api, Property, ApiError } from '@/lib/api';
 import {
   Search,
   Loader2,
   AlertCircle,
   Home,
   MapPin,
   Bed,
   Bath,
   Maximize,
   MessageCircle,
 } from 'lucide-react';
 
 export default function BotPreview() {
   const [results, setResults] = useState<Property[]>([]);
   const [isLoading, setIsLoading] = useState(false);
   const [error, setError] = useState<string | null>(null);
   const [hasSearched, setHasSearched] = useState(false);
 
   // Filter state - dynamic, not hardcoded
   const [filters, setFilters] = useState<Record<string, string>>({});
 
   const handleFilterChange = (key: string, value: string) => {
     setFilters((prev) => {
       const next = { ...prev };
       if (value && value !== 'any') {
         next[key] = value;
       } else {
         delete next[key];
       }
       return next;
     });
   };
 
   const handleSearch = async (e: React.FormEvent) => {
     e.preventDefault();
     setIsLoading(true);
     setError(null);
     setHasSearched(true);
 
     try {
       // Build params dynamically from filters
       const params: Record<string, unknown> = {};
       Object.entries(filters).forEach(([key, value]) => {
         if (value && value !== 'any') {
           params[key] = value;
         }
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
         {/* Header */}
         <div>
           <h1 className="page-header flex items-center gap-2">
             <MessageCircle className="h-7 w-7" />
             Bot Preview
           </h1>
           <p className="text-muted-foreground">
             Preview how properties appear in bot search results (WhatsApp-style cards)
           </p>
         </div>
 
         {/* Search Form */}
         <Card>
           <CardHeader>
             <CardTitle>Search Properties</CardTitle>
           </CardHeader>
           <CardContent>
             <form onSubmit={handleSearch} className="space-y-4">
               <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                 <div className="space-y-2">
                   <Label htmlFor="city">City</Label>
                   <Input
                     id="city"
                     value={filters.city || ''}
                     onChange={(e) => handleFilterChange('city', e.target.value)}
                     placeholder="e.g., Los Angeles"
                   />
                 </div>
 
                 <div className="space-y-2">
                   <Label htmlFor="property_type">Property Type</Label>
                   <Select
                     value={filters.property_type || 'any'}
                     onValueChange={(value) => handleFilterChange('property_type', value)}
                   >
                     <SelectTrigger>
                       <SelectValue placeholder="Any type" />
                     </SelectTrigger>
                     <SelectContent>
                       <SelectItem value="any">Any type</SelectItem>
                        <SelectItem value="apartment">Apartment</SelectItem>
                        <SelectItem value="villa">Villa</SelectItem>
                        <SelectItem value="plot">Plot</SelectItem>
                        <SelectItem value="commercial">Commercial</SelectItem>
                        <SelectItem value="farmhouse">Farmhouse</SelectItem>
                        <SelectItem value="other">Other</SelectItem>
                     </SelectContent>
                   </Select>
                 </div>
 
                 <div className="space-y-2">
                   <Label htmlFor="min_price">Min Price</Label>
                   <Input
                     id="min_price"
                     type="number"
                     min={0}
                     value={filters.min_price || ''}
                     onChange={(e) => handleFilterChange('min_price', e.target.value)}
                     placeholder="e.g., 100000"
                   />
                 </div>
 
                 <div className="space-y-2">
                   <Label htmlFor="max_price">Max Price</Label>
                   <Input
                     id="max_price"
                     type="number"
                     min={0}
                     value={filters.max_price || ''}
                     onChange={(e) => handleFilterChange('max_price', e.target.value)}
                     placeholder="e.g., 500000"
                   />
                 </div>
 
                 <div className="space-y-2">
                    <Label htmlFor="bhk">BHK</Label>
                    <Select
                      value={filters.bhk || 'any'}
                      onValueChange={(value) => handleFilterChange('bhk', value)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Any" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="any">Any</SelectItem>
                        <SelectItem value="1">1 BHK</SelectItem>
                        <SelectItem value="2">2 BHK</SelectItem>
                        <SelectItem value="3">3 BHK</SelectItem>
                        <SelectItem value="4">4 BHK</SelectItem>
                        <SelectItem value="5">5 BHK</SelectItem>
                        <SelectItem value="6">6+ BHK</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
               </div>
 
               <div className="flex gap-2 pt-2">
                 <Button type="submit" disabled={isLoading}>
                   {isLoading ? (
                     <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                   ) : (
                     <Search className="h-4 w-4 mr-2" />
                   )}
                   Search
                 </Button>
                 <Button type="button" variant="outline" onClick={handleClear}>
                   Clear
                 </Button>
               </div>
             </form>
           </CardContent>
         </Card>
 
         {/* Error */}
         {error && (
           <Alert variant="destructive">
             <AlertCircle className="h-4 w-4" />
             <AlertDescription>{error}</AlertDescription>
           </Alert>
         )}
 
         {/* Results - WhatsApp-style cards */}
         {hasSearched && (
           <div className="space-y-4">
             <h2 className="section-header">
               Results ({results.length} {results.length === 1 ? 'property' : 'properties'})
             </h2>
 
             {results.length === 0 ? (
               <Card>
                 <CardContent className="flex flex-col items-center justify-center py-12">
                   <Home className="h-12 w-12 text-muted-foreground/50 mb-4" />
                   <p className="text-muted-foreground">No properties found matching your criteria</p>
                 </CardContent>
               </Card>
             ) : (
               <div className="max-w-xl mx-auto space-y-3">
                 {/* WhatsApp-style chat bubbles */}
                <div className="bg-success/20 rounded-lg p-3 ml-auto max-w-[85%]">
                   <p className="text-sm">
                     🏠 Found {results.length} {results.length === 1 ? 'property' : 'properties'} for you!
                   </p>
                 </div>
 
                 {results.map((property) => (
                   <div
                     key={property.id}
                     className="bg-card border rounded-lg overflow-hidden shadow-sm max-w-[85%]"
                   >
                     {/* Image */}
                     <div className="aspect-video bg-muted flex items-center justify-center overflow-hidden">
                       {property.images?.find(img => img.is_primary)?.image_url || property.images?.[0]?.image_url ? (
                        <img
                          src={property.images.find(img => img.is_primary)?.image_url || property.images[0].image_url}
                          alt={property.title}
                          className="h-full w-full object-cover"
                        />
                       ) : (
                         <Home className="h-12 w-12 text-muted-foreground/50" />
                       )}
                     </div>
 
                     {/* Content */}
                     <div className="p-3 space-y-2">
                       <h3 className="font-semibold">{property.title}</h3>
 
                       {property.city && (
                        <div className="flex items-center gap-1 text-sm text-muted-foreground">
                          <MapPin className="h-3 w-3" />
                          {property.city}
                        </div>
                      )}
 
                       <p className="text-lg font-bold text-accent">
                         {property.price ? `$${property.price.toLocaleString()}` : 'Price on request'}
                       </p>
 
                       <div className="flex gap-4 text-sm text-muted-foreground">
                        {property.bhk !== undefined && property.bhk !== null && (
                          <span className="flex items-center gap-1">
                            <Bed className="h-3 w-3" />
                            {property.bhk} BHK
                          </span>
                        )}
                        {property.area !== undefined && property.area !== null && (
                          <span className="flex items-center gap-1">
                            <Maximize className="h-3 w-3" />
                            {property.area.toLocaleString()} sqft
                          </span>
                        )}
                        {property.property_type && (
                          <span className="flex items-center gap-1 capitalize">
                            {property.property_type}
                          </span>
                        )}
                      </div>
 
                       {property.description && (
                         <p className="text-sm text-muted-foreground line-clamp-2">
                           {property.description}
                         </p>
                       )}
 
                       <span className={property.status === 'sold' ? 'status-sold' : 'status-available'}>
                        {property.status === 'sold' ? 'Sold' : 'Available'}
                      </span>
                     </div>
                   </div>
                 ))}
 
                <div className="bg-success/20 rounded-lg p-3 ml-auto max-w-[85%]">
                   <p className="text-sm">
                     💬 Reply with a property number for more details!
                   </p>
                 </div>
               </div>
             )}
           </div>
         )}
       </div>
     </DashboardLayout>
   );
 }