 import { useEffect, useState } from 'react';
 import { useParams, useNavigate, Link } from 'react-router-dom';
 import { DashboardLayout } from '@/components/layout/DashboardLayout';
 import { Button } from '@/components/ui/button';
 import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
 import { Alert, AlertDescription } from '@/components/ui/alert';
 import {
   AlertDialog,
   AlertDialogAction,
   AlertDialogCancel,
   AlertDialogContent,
   AlertDialogDescription,
   AlertDialogFooter,
   AlertDialogHeader,
   AlertDialogTitle,
   AlertDialogTrigger,
 } from '@/components/ui/alert-dialog';
 import { api, Property, PropertyImage, ApiError } from '@/lib/api';
 import {
   ArrowLeft,
   Edit,
   Trash2,
   CheckCircle,
   Loader2,
   AlertCircle,
   Home,
   MapPin,
   Bed,
   Bath,
   Maximize,
   Upload,
   Star,
   X,
 } from 'lucide-react';
 import { toast } from 'sonner';
 
 export default function PropertyDetail() {
   const { id } = useParams<{ id: string }>();
   const navigate = useNavigate();
   const [property, setProperty] = useState<Property | null>(null);
   const [images, setImages] = useState<PropertyImage[]>([]);
   const [isLoading, setIsLoading] = useState(true);
   const [error, setError] = useState<string | null>(null);
   const [isDeleting, setIsDeleting] = useState(false);
   const [isMarkingSold, setIsMarkingSold] = useState(false);
   const [isUploadingImages, setIsUploadingImages] = useState(false);
 
   useEffect(() => {
     const fetchData = async () => {
       if (!id) return;
 
       try {
         const [propertyData, imagesData] = await Promise.all([
           api.properties.get(id),
           api.images.list(id).catch(() => []),
         ]);
         setProperty(propertyData);
         setImages(imagesData);
       } catch (err) {
         const message = err instanceof ApiError ? err.message : 'Failed to load property';
         setError(message);
       } finally {
         setIsLoading(false);
       }
     };
 
     fetchData();
   }, [id]);
 
   const handleMarkSold = async () => {
     if (!id) return;
     setIsMarkingSold(true);
 
     try {
       const updated = await api.properties.markSold(id);
       setProperty(updated);
       toast.success('Property marked as sold');
     } catch (err) {
       const message = err instanceof ApiError ? err.message : 'Failed to mark as sold';
       toast.error(message);
     } finally {
       setIsMarkingSold(false);
     }
   };
 
   const handleDelete = async () => {
     if (!id) return;
     setIsDeleting(true);
 
     try {
       await api.properties.delete(id);
       toast.success('Property deleted');
       navigate('/properties');
     } catch (err) {
       const message = err instanceof ApiError ? err.message : 'Failed to delete property';
       toast.error(message);
       setIsDeleting(false);
     }
   };
 
   const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
     if (!id || !e.target.files?.length) return;
 
     setIsUploadingImages(true);
     try {
       const files = Array.from(e.target.files);
       const uploadedImages = await api.images.upload(id, files);
       setImages([...images, ...uploadedImages]);
       toast.success(`${files.length} image(s) uploaded`);
     } catch (err) {
       const message = err instanceof ApiError ? err.message : 'Failed to upload images';
       toast.error(message);
     } finally {
       setIsUploadingImages(false);
       e.target.value = '';
     }
   };
 
   const handleSetPrimary = async (imageId: number) => {
     if (!id) return;
 
     try {
        await api.images.setPrimary(id, imageId);
        // Refresh images from server to get updated primary status
        const updatedImages = await api.images.list(id);
        setImages(updatedImages);
        toast.success('Primary image updated');
     } catch (err) {
       const message = err instanceof ApiError ? err.message : 'Failed to set primary image';
       toast.error(message);
     }
   };
 
   const handleDeleteImage = async (imageId: number) => {
     if (!id) return;
 
     try {
       await api.images.delete(id, imageId);
       setImages(images.filter(img => img.id !== imageId));
       toast.success('Image deleted');
     } catch (err) {
       const message = err instanceof ApiError ? err.message : 'Failed to delete image';
       toast.error(message);
     }
   };
 
   if (isLoading) {
     return (
       <DashboardLayout>
         <div className="flex items-center justify-center py-12">
           <Loader2 className="h-8 w-8 animate-spin text-primary" />
         </div>
       </DashboardLayout>
     );
   }
 
   if (error || !property) {
     return (
       <DashboardLayout>
         <Alert variant="destructive">
           <AlertCircle className="h-4 w-4" />
           <AlertDescription>{error || 'Property not found'}</AlertDescription>
         </Alert>
         <Link to="/properties">
           <Button variant="outline" className="mt-4">
             <ArrowLeft className="h-4 w-4 mr-2" />
             Back to Properties
           </Button>
         </Link>
       </DashboardLayout>
     );
   }
 
   return (
     <DashboardLayout>
       <div className="space-y-6 animate-fade-in">
         {/* Header */}
         <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
           <div className="flex items-center gap-4">
             <Link to="/properties">
               <Button variant="ghost" size="icon">
                 <ArrowLeft className="h-5 w-5" />
               </Button>
             </Link>
             <div>
               <h1 className="page-header">{property.title}</h1>
               <div className="flex items-center gap-2 text-muted-foreground">
                 {property.city && (
                  <>
                    <MapPin className="h-4 w-4" />
                    <span>{property.city}</span>
                  </>
                )}
                 <span className={property.status === 'sold' ? 'status-sold' : 'status-available'}>
                  {property.status === 'sold' ? 'Sold' : 'Available'}
                </span>
               </div>
             </div>
           </div>
 
           <div className="flex gap-2">
             {property.status !== 'sold' && (
               <Button
                 variant="outline"
                 onClick={handleMarkSold}
                 disabled={isMarkingSold}
               >
                 {isMarkingSold ? (
                   <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                 ) : (
                   <CheckCircle className="h-4 w-4 mr-2" />
                 )}
                 Mark as Sold
               </Button>
             )}
 
             <Link to={`/properties/${id}/edit`}>
               <Button variant="outline">
                 <Edit className="h-4 w-4 mr-2" />
                 Edit
               </Button>
             </Link>
 
             <AlertDialog>
               <AlertDialogTrigger asChild>
                 <Button variant="destructive">
                   <Trash2 className="h-4 w-4 mr-2" />
                   Delete
                 </Button>
               </AlertDialogTrigger>
               <AlertDialogContent>
                 <AlertDialogHeader>
                   <AlertDialogTitle>Delete Property?</AlertDialogTitle>
                   <AlertDialogDescription>
                     This will soft delete the property. It won't appear in listings anymore.
                   </AlertDialogDescription>
                 </AlertDialogHeader>
                 <AlertDialogFooter>
                   <AlertDialogCancel>Cancel</AlertDialogCancel>
                   <AlertDialogAction onClick={handleDelete} disabled={isDeleting}>
                     {isDeleting ? 'Deleting...' : 'Delete'}
                   </AlertDialogAction>
                 </AlertDialogFooter>
               </AlertDialogContent>
             </AlertDialog>
           </div>
         </div>
 
         <div className="grid gap-6 lg:grid-cols-3">
           {/* Main Info */}
           <div className="lg:col-span-2 space-y-6">
             {/* Image Gallery */}
             <Card>
               <CardHeader className="flex flex-row items-center justify-between">
                 <CardTitle>Images</CardTitle>
                 <label>
                   <Button variant="outline" size="sm" disabled={isUploadingImages} asChild>
                     <span className="cursor-pointer">
                       {isUploadingImages ? (
                         <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                       ) : (
                         <Upload className="h-4 w-4 mr-2" />
                       )}
                       Upload
                     </span>
                   </Button>
                   <input
                     type="file"
                     multiple
                     accept="image/*"
                     className="hidden"
                     onChange={handleImageUpload}
                     disabled={isUploadingImages}
                   />
                 </label>
               </CardHeader>
               <CardContent>
                 {images.length === 0 ? (
                   <div className="aspect-video rounded-lg bg-muted flex flex-col items-center justify-center">
                     <Home className="h-12 w-12 text-muted-foreground/50 mb-2" />
                     <p className="text-muted-foreground">No images uploaded</p>
                   </div>
                 ) : (
                   <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                     {images.map((image) => (
                       <div
                         key={image.id}
                         className="relative aspect-video rounded-lg overflow-hidden group"
                       >
                         <img
                           src={image.image_url}
                           alt="Property"
                           className="h-full w-full object-cover"
                         />
                         {image.is_primary && (
                           <div className="absolute top-2 left-2 bg-accent text-accent-foreground px-2 py-0.5 rounded text-xs font-medium flex items-center gap-1">
                             <Star className="h-3 w-3" />
                             Primary
                           </div>
                         )}
                         <div className="absolute inset-0 bg-foreground/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                           {!image.is_primary && (
                             <Button
                               size="sm"
                               variant="secondary"
                               onClick={() => handleSetPrimary(image.id)}
                             >
                               <Star className="h-4 w-4" />
                             </Button>
                           )}
                           <Button
                             size="sm"
                             variant="destructive"
                             onClick={() => handleDeleteImage(image.id)}
                           >
                             <X className="h-4 w-4" />
                           </Button>
                         </div>
                       </div>
                     ))}
                   </div>
                 )}
               </CardContent>
             </Card>
 
             {/* Description */}
             {property.description && (
               <Card>
                 <CardHeader>
                   <CardTitle>Description</CardTitle>
                 </CardHeader>
                 <CardContent>
                   <p className="text-muted-foreground whitespace-pre-wrap">
                     {property.description}
                   </p>
                 </CardContent>
               </Card>
             )}
           </div>
 
           {/* Sidebar */}
           <div className="space-y-6">
             <Card>
               <CardHeader>
                 <CardTitle>Price</CardTitle>
               </CardHeader>
               <CardContent>
                 <p className="text-3xl font-bold text-accent">
                   {property.price ? `$${property.price.toLocaleString()}` : 'Price TBD'}
                 </p>
               </CardContent>
             </Card>
 
             <Card>
               <CardHeader>
                 <CardTitle>Details</CardTitle>
               </CardHeader>
               <CardContent className="space-y-4">
                 {property.property_type && (
                   <div className="flex items-center gap-3">
                     <Home className="h-5 w-5 text-muted-foreground" />
                     <div>
                       <p className="text-sm text-muted-foreground">Type</p>
                       <p className="font-medium">{property.property_type}</p>
                     </div>
                   </div>
                 )}
 
                 {property.bhk !== undefined && property.bhk !== null && (
  <div className="flex items-center gap-3">
    <Bed className="h-5 w-5 text-muted-foreground" />
    <div>
      <p className="text-sm text-muted-foreground">BHK</p>
      <p className="font-medium">{property.bhk ?? 0} BHK</p>
    </div>
  </div>
)}

                {property.area !== undefined && property.area !== null && (
                  <div className="flex items-center gap-3">
                    <Maximize className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="text-sm text-muted-foreground">Area</p>
                      <p className="font-medium">{property.area.toLocaleString()} sqft</p>
                    </div>
                  </div>
                )}

                {property.emi_available && (
                  <>
                    <div className="flex items-center gap-3">
                      <div>
                        <p className="text-sm text-muted-foreground">EMI Available</p>
                        <p className="font-medium">Yes</p>
                      </div>
                    </div>
                    {property.emi_amount && (
                      <div className="flex items-center gap-3">
                        <div>
                          <p className="text-sm text-muted-foreground">EMI Amount</p>
                          <p className="font-medium">${property.emi_amount.toLocaleString()}</p>
                        </div>
                      </div>
                    )}
                    {property.expected_roi && (
                      <div className="flex items-center gap-3">
                        <div>
                          <p className="text-sm text-muted-foreground">Expected ROI</p>
                          <p className="font-medium">{property.expected_roi ?? 0}%</p>
                        </div>
                      </div>
                    )}
                  </>
                )}
               </CardContent>
             </Card>
 
             {property.city && (
              <Card>
                <CardHeader>
                  <CardTitle>Location</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-start gap-3">
                    <MapPin className="h-5 w-5 text-muted-foreground mt-0.5" />
                    <div>
                      <p>{property.city}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
           </div>
         </div>
       </div>
     </DashboardLayout>
   );
 }