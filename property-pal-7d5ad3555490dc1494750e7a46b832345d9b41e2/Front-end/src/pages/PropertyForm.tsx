 import { useEffect, useState } from 'react';
 import { useParams, useNavigate, Link } from 'react-router-dom';
 import { DashboardLayout } from '@/components/layout/DashboardLayout';
 import { Button } from '@/components/ui/button';
 import { Input } from '@/components/ui/input';
 import { Textarea } from '@/components/ui/textarea';
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
 import { api, Property, PropertyCreate, ApiError } from '@/lib/api';
 import { ArrowLeft, Loader2, AlertCircle, Save } from 'lucide-react';
 import { toast } from 'sonner';
 
 const propertyTypes = [
  { value: 'apartment', label: 'Apartment' },
  { value: 'villa', label: 'Villa' },
  { value: 'plot', label: 'Plot' },
  { value: 'commercial', label: 'Commercial' },
  { value: 'farmhouse', label: 'Farmhouse' },
  { value: 'other', label: 'Other' },
];
 
 export default function PropertyForm() {
   const { id } = useParams<{ id: string }>();
   const navigate = useNavigate();
   const isEditing = !!id;
 
   const [isLoading, setIsLoading] = useState(isEditing);
   const [isSubmitting, setIsSubmitting] = useState(false);
   const [error, setError] = useState<string | null>(null);
   const [emiAvailable, setEmiAvailable] = useState(false); 
   const [formData, setFormData] = useState<PropertyCreate>({
    title: '',
    description: '',
    property_type: '',
    area_sqft: undefined,
    bedrooms: undefined,
    bathrooms: undefined,
    kitchen: undefined,
    dining_hall: undefined,
    hall: undefined,
    terrace: undefined,
    price: undefined,
    expected_roi: undefined,
    address: '',
    city: '',
    state: '',
    zip_code: '',
    currency: 'AED',
  });
 
   useEffect(() => {
     if (isEditing && id) {
       const fetchProperty = async () => {
         try {
           const property = await api.properties.get(id);
           setFormData({
             title: property.title || '',
             description: property.description || '',
             property_type: property.property_type || '',
             price: property.price,
             bedrooms: property.bedrooms ?? property.bhk,
             bathrooms: property.bathrooms,
             area_sqft: property.area_sqft ?? property.area,
             kitchen: property.kitchen,
             dining_hall: property.dining_hall,
             hall: property.hall,
             terrace: property.terrace,
             expected_roi: property.expected_roi,
             address: property.address || '',
             city: property.city || '',
             state: property.state || '',
             zip_code: property.zip_code || '',
             currency: property.currency || 'AED',
           });
           setEmiAvailable(property.emi_available === true);
         } catch (err) {
            let message = 'Failed to save property';
            if (err instanceof ApiError) {
              message = typeof err.message === 'string' ? err.message : JSON.stringify(err.message);
            }
            setError(message);
          } finally {
           setIsLoading(false);
         }
       };
 
       fetchProperty();
     }
   }, [id, isEditing]);
 
   const handleChange = (
     e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
   ) => {
     const { name, value, type } = e.target;
     setFormData((prev) => ({
       ...prev,
       [name]: type === 'number' ? (value ? Number(value) : undefined) : value,
     }));
   };
 
   const handleSelectChange = (name: string, value: string) => {
     setFormData((prev) => ({ ...prev, [name]: value }));
   };
 
   const handleSubmit = async (e: React.FormEvent) => {
     e.preventDefault();
     setError(null);
 
     if (!formData.title.trim()) {
       setError('Title is required');
       return;
     }
     if (!formData.property_type) {
        setError('Property type is required');
        return;
     }
 
     setIsSubmitting(true);
 
     try {
       let result: Property;
       if (isEditing && id) {
         result = await api.properties.update(id, { ...formData, emi_available: emiAvailable });
         toast.success('Property updated successfully');
       } else {
         result = await api.properties.create({ ...formData, emi_available: emiAvailable });
         toast.success('Property created successfully');
       }
       navigate(`/properties/${result.id}`);
     } catch (err) {
       const message = err instanceof ApiError ? err.message : 'Failed to save property';
       setError(message);
     } finally {
       setIsSubmitting(false);
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
 
   return (
     <DashboardLayout>
       <div className="max-w-3xl mx-auto space-y-6 animate-fade-in">
         {/* Header */}
         <div className="flex items-center gap-4">
           <Link to={isEditing ? `/properties/${id}` : '/properties'}>
             <Button variant="ghost" size="icon">
               <ArrowLeft className="h-5 w-5" />
             </Button>
           </Link>
           <h1 className="page-header">
             {isEditing ? 'Edit Property' : 'Add New Property'}
           </h1>
         </div>
 
         <form onSubmit={handleSubmit}>
           <Card>
             <CardHeader>
               <CardTitle>Property Details</CardTitle>
             </CardHeader>
             <CardContent className="space-y-6">
               {error && (
                 <Alert variant="destructive">
                   <AlertCircle className="h-4 w-4" />
                   <AlertDescription>{error}</AlertDescription>
                 </Alert>
               )}
 
               {/* Basic Info */}
               <div className="space-y-4">
                 <div className="space-y-2">
                   <Label htmlFor="title">Title *</Label>
                   <Input
                     id="title"
                     name="title"
                     value={formData.title}
                     onChange={handleChange}
                     placeholder="e.g., Beautiful Family Home"
                     required
                   />
                 </div>
 
                 <div className="space-y-2">
                   <Label htmlFor="description">Description</Label>
                   <Textarea
                     id="description"
                     name="description"
                     value={formData.description}
                     onChange={handleChange}
                     placeholder="Describe the property..."
                     rows={4}
                   />
                 </div>
 
                 <div className="grid gap-4 sm:grid-cols-2">
                   
                 </div>
               </div>
 
               {/* Property Features */}
               <div className="space-y-4">
                 <h3 className="section-header">Features</h3>
                 <div className="grid gap-4 sm:grid-cols-3">
                  <div className="space-y-2">
                     <Label htmlFor="property_type">Property Type</Label>
                     <Select
                       value={formData.property_type}
                       onValueChange={(value) => handleSelectChange('property_type', value)}
                     >
                       <SelectTrigger>
                         <SelectValue placeholder="Select type" />
                       </SelectTrigger>
                       <SelectContent>
                         {propertyTypes.map((type) => (
                          <SelectItem key={type.value} value={type.value}>
                            {type.label}
                          </SelectItem>
                        ))}
                       </SelectContent>
                     </Select>
                   </div>
                   <div className="space-y-2">
                     <Label htmlFor="area_sqft">Area (sqft)</Label>
                     <Input
                       id="area_sqft"
                       name="area_sqft"
                       type="number"
                       min={0}
                       value={formData.area_sqft ?? ''}
                       onChange={handleChange}
                       placeholder="e.g., 2000"
                     />
                   </div>
                   
                   <div className="space-y-2">
                     <Label htmlFor="bedrooms">Bedrooms</Label>
                     <Input
                       id="bedrooms"
                       name="bedrooms"
                       type="number"
                       min={0}
                       value={formData.bedrooms ?? ''}
                       onChange={handleChange}
                       placeholder="e.g., 3"
                     />
                   </div>
                   
 
                   <div className="space-y-2">
                     <Label htmlFor="bathrooms">Bathrooms</Label>
                     <Input
                       id="bathrooms"
                       name="bathrooms"
                       type="number"
                       min={0}
                       step={0.5}
                       value={formData.bathrooms ?? ''}
                       onChange={handleChange}
                       placeholder="e.g., 2"
                     />
                   </div>
 
                   
                   <div className="space-y-2">
                     <Label htmlFor="kitchen">Kitchen</Label>
                     <Input
                       id="kitchen"
                       name="kitchen"
                       type="number"
                       min={0}
                       value={formData.kitchen ?? ''}
                       onChange={handleChange}
                       placeholder="e.g., 1"
                     />
                   </div>
                   <div className="space-y-2">
                     <Label htmlFor="dining_hall">Dining Hall</Label>
                     <Input
                       id="dining_hall"
                       name="dining_hall"
                       type="number"
                       min={0}
                       value={formData.dining_hall ?? ''}
                       onChange={handleChange}
                       placeholder="e.g., 1"
                     />
                   </div>
                   <div className="space-y-2">
                     <Label htmlFor="hall">Hall / Living Hall</Label>
                     <Input
                       id="hall"
                       name="hall"
                       type="number"
                       min={0}
                       value={formData.hall ?? ''}
                       onChange={handleChange}
                       placeholder="e.g., 1"
                     />
                   </div>
                   <div className="space-y-2">
                     <Label>Terrace</Label>
                     <Select
                       value={formData.terrace === true ? 'yes' : formData.terrace === false ? 'no' : ''}
                       onValueChange={(v) => setFormData(prev => ({ ...prev, terrace: v === 'yes' }))}
                     >
                       <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                       <SelectContent>
                         <SelectItem value="yes">Yes</SelectItem>
                         <SelectItem value="no">No</SelectItem>
                       </SelectContent>
                     </Select>
                   </div>
                 </div>
               </div>
 
               {/* Location */}
               <div className="space-y-4">
                 <h3 className="section-header">Location</h3>
              
                 <div className="space-y-2">
                   <Label htmlFor="address">Street Address</Label>
                   <Input
                     id="address"
                     name="address"
                     value={formData.address}
                     onChange={handleChange}
                     placeholder="e.g., 123 Main Street"
                   />
                 </div>
 
                 <div className="grid gap-4 sm:grid-cols-3">
                   <div className="space-y-2">
                     <Label htmlFor="city">City</Label>
                     <Input
                       id="city"
                       name="city"
                       value={formData.city}
                       onChange={handleChange}
                       placeholder="e.g., Los Angeles"
                     />
                   </div>
 
                   <div className="space-y-2">
                     <Label htmlFor="state">State</Label>
                     <Input
                       id="state"
                       name="state"
                       value={formData.state}
                       onChange={handleChange}
                       placeholder="e.g., CA"
                     />
                   </div>
 
                   <div className="space-y-2">
                     <Label htmlFor="zip_code">ZIP Code</Label>
                     <Input
                       id="zip_code"
                       name="zip_code"
                       value={formData.zip_code}
                       onChange={handleChange}
                       placeholder="e.g., 90001"
                     />
                   </div>
                 </div>
               </div>


               {/* Investment Details */}
              <div className="space-y-4">
                <h3 className="section-header">Investment Details</h3>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Currency</Label>
                    <Select
                      value={formData.currency ?? 'AED'}
                      onValueChange={(value) => handleSelectChange('currency', value)}
                    >
                      <SelectTrigger><SelectValue placeholder="Select currency" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="AED">AED (د.إ)</SelectItem>
                        <SelectItem value="USD">USD ($)</SelectItem>
                        <SelectItem value="GBP">GBP (£)</SelectItem>
                        <SelectItem value="INR">INR (₹)</SelectItem>
                        <SelectItem value="EUR">EUR (€)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                     <Label htmlFor="price">Price ({formData.currency ?? 'AED'})</Label>
                     <Input
                       id="price"
                       name="price"
                       type="number"
                       min={0}
                       value={formData.price ?? ''}
                       onChange={handleChange}
                       placeholder="e.g., 450000"
                     />
                   </div>
                  <div className="space-y-2">
                    <Label htmlFor="expected_roi">ROI %</Label>
                    <Input
                      id="expected_roi"
                      name="expected_roi"
                      type="number"
                      min={0}
                      step={0.01}
                      value={formData.expected_roi ?? ''}
                      onChange={handleChange}
                      placeholder="e.g., 8.5"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>EMI Available?</Label>
                    <Select
                      value={emiAvailable ? 'yes' : 'no'}
                      onValueChange={(value) => setEmiAvailable(value === 'yes')}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="yes">Yes</SelectItem>
                        <SelectItem value="no">No</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>
 
               {/* Submit */}
               <div className="flex gap-4 pt-4">
                 <Button type="submit" disabled={isSubmitting}>
                   {isSubmitting ? (
                     <>
                       <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                       Saving...
                     </>
                   ) : (
                     <>
                       <Save className="h-4 w-4 mr-2" />
                       {isEditing ? 'Update Property' : 'Create Property'}
                     </>
                   )}
                 </Button>
                 <Link to={isEditing ? `/properties/${id}` : '/properties'}>
                   <Button type="button" variant="outline">
                     Cancel
                   </Button>
                 </Link>
               </div>
             </CardContent>
           </Card>
         </form>
       </div>
     </DashboardLayout>
   );
 }