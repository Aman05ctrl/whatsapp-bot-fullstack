 import { useEffect, useState } from 'react';
 import { Link } from 'react-router-dom';
 import { DashboardLayout } from '@/components/layout/DashboardLayout';
 import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
 import { Button } from '@/components/ui/button';
 import { api, Property, ApiError } from '@/lib/api';
 import { 
   Home, 
   DollarSign, 
   CheckCircle, 
   TrendingUp, 
   Plus,
   Loader2,
   AlertCircle
 } from 'lucide-react';
 import { Alert, AlertDescription } from '@/components/ui/alert';
 
 export default function Dashboard() {
   const [properties, setProperties] = useState<Property[]>([]);
   const [isLoading, setIsLoading] = useState(true);
   const [error, setError] = useState<string | null>(null);
 
   useEffect(() => {
     const fetchProperties = async () => {
       try {
         const response = await api.properties.list({ size: 100 });
         setProperties(response.properties || []);
       } catch (err) {
         const message = err instanceof ApiError ? err.message : 'Failed to load properties';
         setError(message);
       } finally {
         setIsLoading(false);
       }
     };
 
     fetchProperties();
   }, []);
 
   const stats = {
  total: properties.length,
  available: properties.filter(p => p.status === 'active').length,
  sold: properties.filter(p => p.status === 'sold').length,
  totalValue: properties
    .filter(p => p.status !== 'inactive' && p.price)
    .reduce((sum, p) => sum + (p.price || 0), 0),
};
 
   const recentProperties = properties
  .filter(p => p.status !== 'inactive')
  .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  .slice(0, 5);
 
   return (
     <DashboardLayout>
       <div className="space-y-6 animate-fade-in">
         {/* Header */}
         <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
           <div>
             <h1 className="page-header">Dashboard</h1>
             <p className="text-muted-foreground">Welcome back! Here's your property overview.</p>
           </div>
           <Link to="/properties/new">
             <Button className="gap-2">
               <Plus className="h-4 w-4" />
               Add Property
             </Button>
           </Link>
         </div>
 
         {error && (
           <Alert variant="destructive">
             <AlertCircle className="h-4 w-4" />
             <AlertDescription>{error}</AlertDescription>
           </Alert>
         )}
 
         {isLoading ? (
           <div className="flex items-center justify-center py-12">
             <Loader2 className="h-8 w-8 animate-spin text-primary" />
           </div>
         ) : (
           <>
             {/* Stats Grid */}
             <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
               <Card>
                 <CardHeader className="flex flex-row items-center justify-between pb-2">
                   <CardTitle className="text-sm font-medium text-muted-foreground">
                     Total Properties
                   </CardTitle>
                   <Home className="h-4 w-4 text-muted-foreground" />
                 </CardHeader>
                 <CardContent>
                   <div className="text-2xl font-bold">{stats.total}</div>
                 </CardContent>
               </Card>
 
               <Card>
                 <CardHeader className="flex flex-row items-center justify-between pb-2">
                   <CardTitle className="text-sm font-medium text-muted-foreground">
                     Available
                   </CardTitle>
                   <TrendingUp className="h-4 w-4 text-success" />
                 </CardHeader>
                 <CardContent>
                   <div className="text-2xl font-bold text-success">{stats.available}</div>
                 </CardContent>
               </Card>
 
               <Card>
                 <CardHeader className="flex flex-row items-center justify-between pb-2">
                   <CardTitle className="text-sm font-medium text-muted-foreground">
                     Sold
                   </CardTitle>
                   <CheckCircle className="h-4 w-4 text-muted-foreground" />
                 </CardHeader>
                 <CardContent>
                   <div className="text-2xl font-bold">{stats.sold}</div>
                 </CardContent>
               </Card>
 
               <Card>
                 <CardHeader className="flex flex-row items-center justify-between pb-2">
                   <CardTitle className="text-sm font-medium text-muted-foreground">
                     Total Value
                   </CardTitle>
                   <DollarSign className="h-4 w-4 text-accent" />
                 </CardHeader>
                 <CardContent>
                   <div className="text-2xl font-bold text-accent">
                     ${stats.totalValue.toLocaleString()}
                   </div>
                 </CardContent>
               </Card>
             </div>
 
             {/* Recent Properties */}
             <Card>
               <CardHeader>
                 <CardTitle>Recent Properties</CardTitle>
                 <CardDescription>Your most recently added properties</CardDescription>
               </CardHeader>
               <CardContent>
                 {recentProperties.length === 0 ? (
                   <div className="text-center py-8 text-muted-foreground">
                     <Home className="h-12 w-12 mx-auto mb-4 opacity-50" />
                     <p>No properties yet. Add your first property to get started.</p>
                     <Link to="/properties/new">
                       <Button variant="outline" className="mt-4">
                         <Plus className="h-4 w-4 mr-2" />
                         Add Property
                       </Button>
                     </Link>
                   </div>
                 ) : (
                   <div className="space-y-4">
                     {recentProperties.map((property) => (
                       <Link
                         key={property.id}
                         to={`/properties/${property.id}`}
                         className="flex items-center gap-4 p-3 rounded-lg hover:bg-muted/50 transition-colors"
                       >
                         <div className="h-12 w-12 rounded-lg bg-muted flex items-center justify-center overflow-hidden">
                           {property.images?.find(img => img.is_primary)?.image_url || property.images?.[0]?.image_url ? (
                            <img
                              src={property.images.find(img => img.is_primary)?.image_url || property.images[0].image_url}
                              alt={property.title}
                              className="h-full w-full object-cover"
                            />
                           ) : (
                             <Home className="h-6 w-6 text-muted-foreground" />
                           )}
                         </div>
                         <div className="flex-1 min-w-0">
                           <p className="font-medium truncate">{property.title}</p>
                           <p className="text-sm text-muted-foreground truncate">
                            {property.city || 'No location'}
                          </p>
                         </div>
                         <div className="text-right">
                           <p className="font-semibold">
                             {property.price 
                               ? `$${property.price.toLocaleString()}` 
                               : 'No price'}
                           </p>
                           <span className={property.status === 'sold' ? 'status-sold' : 'status-available'}>
                              {property.status === 'sold' ? 'Sold' : 'Available'}
                           </span>
                         </div>
                       </Link>
                     ))}
                   </div>
                 )}
               </CardContent>
             </Card>
           </>
         )}
       </div>
     </DashboardLayout>
   );
 }