 import { useState } from 'react';
 import { Link, useNavigate, useLocation } from 'react-router-dom';
 import { useAuth } from '@/contexts/AuthContext';
 import { Button } from '@/components/ui/button';
 import { Input } from '@/components/ui/input';
 import { Label } from '@/components/ui/label';
 import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
 import { Alert, AlertDescription } from '@/components/ui/alert';
 import { Building2, Loader2, AlertCircle } from 'lucide-react';
 
 export default function Login() {
   const [email, setEmail] = useState('');
   const [password, setPassword] = useState('');
   const [isSubmitting, setIsSubmitting] = useState(false);
   const { login, error, clearError } = useAuth();
   const navigate = useNavigate();
   const location = useLocation();
 
   const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/dashboard';
 
   const handleSubmit = async (e: React.FormEvent) => {
     e.preventDefault();
     setIsSubmitting(true);
     clearError();
 
     try {
       await login(email, password);
       navigate(from, { replace: true });
     } catch {
       // Error is handled by context
     } finally {
       setIsSubmitting(false);
     }
   };
 
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
             <CardTitle>Welcome back</CardTitle>
             <CardDescription>Sign in to access your dashboard</CardDescription>
           </CardHeader>
           <form onSubmit={handleSubmit}>
             <CardContent className="space-y-4">
               {error && (
                 <Alert variant="destructive">
                   <AlertCircle className="h-4 w-4" />
                   <AlertDescription>{error}</AlertDescription>
                 </Alert>
               )}
 
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
                   autoComplete="current-password"
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
                     Signing in...
                   </>
                 ) : (
                   'Sign in'
                 )}
               </Button>
 
               <p className="text-sm text-muted-foreground">
                 Don't have an account?{' '}
                 <Link to="/register" className="text-primary hover:underline">
                   Create one
                 </Link>
               </p>
             </CardFooter>
           </form>
         </Card>
       </div>
     </div>
   );
 }