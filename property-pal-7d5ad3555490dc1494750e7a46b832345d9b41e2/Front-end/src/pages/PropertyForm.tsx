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
import { api, Property, ApiError } from '@/lib/api';
import { ArrowLeft, Loader2, AlertCircle, Save } from 'lucide-react';
import { toast } from 'sonner';

// ✅ CORRECTED: Backend property types (lowercase enum values)
const propertyTypes = [
  { value: 'apartment', label: 'Apartment' },
  { value: 'villa', label: 'Villa' },
  { value: 'plot', label: 'Plot' },
  { value: 'commercial', label: 'Commercial' },
  { value: 'farmhouse', label: 'Farmhouse' },
  { value: 'other', label: 'Other' },
];

// ✅ CORRECTED: Form data interface matching backend schema
interface PropertyFormData {
  title: string;
  description: string;
  city: string;
  area: string;
  price: string;
  property_type: string;
  bhk: string;
  emi_available: boolean;
  emi_amount: string;
  expected_roi: string;
}

export default function PropertyForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEditing = !!id;

  const [isLoading, setIsLoading] = useState(isEditing);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ✅ CORRECTED: Form state matching backend fields
  const [formData, setFormData] = useState<PropertyFormData>({
    title: '',
    description: '',
    city: '',
    area: '',
    price: '',
    property_type: 'apartment',
    bhk: '',
    emi_available: false,
    emi_amount: '',
    expected_roi: '',
  });

  useEffect(() => {
    if (isEditing && id) {
      const fetchProperty = async () => {
        try {
          const property = await api.properties.get(id);
          
          // ✅ CORRECTED: Map backend response to form state
          setFormData({
            title: property.title || '',
            description: property.description || '',
            city: property.city || '',
            area: property.area?.toString() || '',
            price: property.price?.toString() || '',
            property_type: property.property_type || 'apartment',
            bhk: property.bhk?.toString() || '',
            emi_available: property.emi_available ?? false,
            emi_amount: property.emi_amount?.toString() || '',
            expected_roi: property.expected_roi?.toString() || '',
          });
        } catch (err) {
          const message = err instanceof ApiError ? err.message : 'Failed to load property';
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
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSelectChange = (name: string, value: string) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleCheckboxChange = (name: string, checked: boolean) => {
    setFormData((prev) => ({ ...prev, [name]: checked }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!formData.title.trim()) {
      setError('Title is required');
      return;
    }
    if (!formData.city.trim()) {
      setError('City is required');
      return;
    }
    if (!formData.area || parseFloat(formData.area) <= 0) {
      setError('Valid area is required');
      return;
    }
    if (!formData.price || parseFloat(formData.price) <= 0) {
      setError('Valid price is required');
      return;
    }

    setIsSubmitting(true);

    try {
      // ✅ CORRECTED: Prepare data matching backend schema EXACTLY
      const propertyData = {
        title: formData.title,
        description: formData.description || undefined,
        city: formData.city,
        area: parseFloat(formData.area),
        price: parseFloat(formData.price),
        property_type: formData.property_type as 'apartment' | 'villa' | 'plot' | 'commercial' | 'farmhouse' | 'other',
        bhk: formData.bhk ? parseInt(formData.bhk) : undefined,
        emi_available: formData.emi_available,
        emi_amount: formData.emi_amount ? parseFloat(formData.emi_amount) : undefined,
        expected_roi: formData.expected_roi ? parseFloat(formData.expected_roi) : undefined,
      };

      let result: Property;
      if (isEditing && id) {
        result = await api.properties.update(id, propertyData);
        toast.success('Property updated successfully');
      } else {
        result = await api.properties.create(propertyData);
        toast.success('Property created successfully');
      }
      navigate(`/properties/${result.id}`);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to save property';
      setError(message);
      toast.error(message);
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
                    placeholder="e.g., Luxury Villa in Noida"
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
                  <div className="space-y-2">
                    <Label htmlFor="property_type">Property Type *</Label>
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
                    <Label htmlFor="city">City *</Label>
                    <Input
                      id="city"
                      name="city"
                      value={formData.city}
                      onChange={handleChange}
                      placeholder="e.g., Noida"
                      required
                    />
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="price">Price ($) *</Label>
                    <Input
                      id="price"
                      name="price"
                      type="number"
                      min={0}
                      step="0.01"
                      value={formData.price}
                      onChange={handleChange}
                      placeholder="e.g., 15000000"
                      required
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="area">Area (sqft) *</Label>
                    <Input
                      id="area"
                      name="area"
                      type="number"
                      min={0}
                      step="0.01"
                      value={formData.area}
                      onChange={handleChange}
                      placeholder="e.g., 2500"
                      required
                    />
                  </div>
                </div>
              </div>

              {/* Property Features */}
              <div className="space-y-4">
                <h3 className="section-header">Features</h3>
                <div className="space-y-2">
                  <Label htmlFor="bhk">BHK (Bedrooms)</Label>
                  <Input
                    id="bhk"
                    name="bhk"
                    type="number"
                    min={1}
                    max={10}
                    value={formData.bhk}
                    onChange={handleChange}
                    placeholder="e.g., 4"
                  />
                </div>
              </div>

              {/* EMI Details */}
              <div className="space-y-4">
                <h3 className="section-header">EMI Options</h3>
                
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="emi_available"
                    checked={formData.emi_available}
                    onChange={(e) => handleCheckboxChange('emi_available', e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300"
                  />
                  <Label htmlFor="emi_available" className="cursor-pointer">
                    EMI Available
                  </Label>
                </div>

                {formData.emi_available && (
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="emi_amount">EMI Amount ($)</Label>
                      <Input
                        id="emi_amount"
                        name="emi_amount"
                        type="number"
                        min={0}
                        step="0.01"
                        value={formData.emi_amount}
                        onChange={handleChange}
                        placeholder="e.g., 125000"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="expected_roi">Expected ROI (%)</Label>
                      <Input
                        id="expected_roi"
                        name="expected_roi"
                        type="number"
                        min={0}
                        max={100}
                        step="0.1"
                        value={formData.expected_roi}
                        onChange={handleChange}
                        placeholder="e.g., 12.5"
                      />
                    </div>
                  </div>
                )}
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