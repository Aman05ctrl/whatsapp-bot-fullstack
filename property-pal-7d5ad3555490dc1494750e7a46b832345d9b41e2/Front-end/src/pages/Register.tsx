 import { useState } from 'react';
 import { Link, useNavigate } from 'react-router-dom';
 import { useAuth } from '@/contexts/AuthContext';
 import { Button } from '@/components/ui/button';
 import { Input } from '@/components/ui/input';
 import { Label } from '@/components/ui/label';
 import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
 import { Alert, AlertDescription } from '@/components/ui/alert';
 import { Building2, Loader2, AlertCircle } from 'lucide-react';
 
 export default function Register() {
   const [fullName, setFullName] = useState('');
   const [email, setEmail] = useState('');
   const [password, setPassword] = useState('');
   const [confirmPassword, setConfirmPassword] = useState('');
   const [localError, setLocalError] = useState('');
   const [isSubmitting, setIsSubmitting] = useState(false);
   const { register, error, clearError } = useAuth();
   const navigate = useNavigate();
 
   const handleSubmit = async (e: React.FormEvent) => {
     e.preventDefault();
     setLocalError('');
     clearError();
 
     if (password !== confirmPassword) {
       setLocalError('Passwords do not match');
       return;
     }
 
     if (password.length < 6) {
       setLocalError('Password must be at least 6 characters');
       return;
     }
 
     setIsSubmitting(true);
 
     try {
       await register(email, password, fullName || undefined);
       navigate('/dashboard', { replace: true });
     } catch {
       // Error is handled by context
     } finally {
       setIsSubmitting(false);
     }
   };
 
   const displayError = localError || error;
 
   return (
     <div className="flex min-h-screen items-center justify-center bg-background px-4">
       <div className="w-full max-w-md animate-fade-in">
         <div className="mb-8 text-center">
           <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-primary">
             <Building2 className="h-8 w-8 text-primary-foreground" />
           </div>
           <h1 className="text-2xl font-bold text-foreground">a_toggle Real Estate</h1>
           <p className="text-muted-foreground">Property Management System</p>
         </div>
 
         <Card>
           <CardHeader>
             <CardTitle>Create an account</CardTitle>
             <CardDescription>Get started with property management</CardDescription>
           </CardHeader>
           <form onSubmit={handleSubmit}>
             <CardContent className="space-y-4">
               {displayError && (
                 <Alert variant="destructive">
                   <AlertCircle className="h-4 w-4" />
                   <AlertDescription>{displayError}</AlertDescription>
                 </Alert>
               )}
 
               <div className="space-y-2">
                 <Label htmlFor="fullName">Full Name (optional)</Label>
                 <Input
                   id="fullName"
                   type="text"
                   placeholder="John Doe"
                   value={fullName}
                   onChange={(e) => setFullName(e.target.value)}
                   autoComplete="name"
                 />
               </div>
 
               <div className="space-y-2">
                 <Label htmlFor="email">Email</Label>
                 <Input
                   id="email"
                   type="email"
                   placeholder="you@example.com"
                   value={email}
                   onChange={(e) => setEmail(e.target.value)}
                   required
                   autoComplete="email"
                 />
               </div>
 
               <div className="space-y-2">
                 <Label htmlFor="password">Password</Label>
                 <Input
                   id="password"
                   type="password"
                   placeholder="••••••••"
                   value={password}
                   onChange={(e) => setPassword(e.target.value)}
                   required
                   autoComplete="new-password"
                 />
               </div>
 
               <div className="space-y-2">
                 <Label htmlFor="confirmPassword">Confirm Password</Label>
                 <Input
                   id="confirmPassword"
                   type="password"
                   placeholder="••••••••"
                   value={confirmPassword}
                   onChange={(e) => setConfirmPassword(e.target.value)}
                   required
                   autoComplete="new-password"
                 />
               </div>
             </CardContent>
 
             <CardFooter className="flex flex-col gap-4">
               <Button 
                 type="submit" 
                 className="w-full" 
                 disabled={isSubmitting}
               >
                 {isSubmitting ? (
                   <>
                     <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                     Creating account...
                   </>
                 ) : (
                   'Create account'
                 )}
               </Button>
 
               <p className="text-sm text-muted-foreground">
                 Already have an account?{' '}
                 <Link to="/login" className="text-primary hover:underline">
                   Sign in
                 </Link>
               </p>
             </CardFooter>
           </form>
         </Card>
       </div>
     </div>
   );
 }