 import { useState } from 'react';
 import { Link, useLocation, useNavigate } from 'react-router-dom';
 import { useAuth } from '@/contexts/AuthContext';
 import { Button } from '@/components/ui/button';
 import {
   DropdownMenu,
   DropdownMenuContent,
   DropdownMenuItem,
   DropdownMenuLabel,
   DropdownMenuSeparator,
   DropdownMenuTrigger,
 } from '@/components/ui/dropdown-menu';
 import {
   Building2,
   LayoutDashboard,
   Home,
   Bot,
   Menu,
   X,
   LogOut,
   User,
   ChevronDown,
 } from 'lucide-react';
 import { cn } from '@/lib/utils';
 
 interface DashboardLayoutProps {
   children: React.ReactNode;
 }
 
 const navItems = [
   { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
   { name: 'Properties', href: '/properties', icon: Home },
   { name: 'Bot Preview', href: '/bot-preview', icon: Bot },
 ];
 
 export function DashboardLayout({ children }: DashboardLayoutProps) {
   const [sidebarOpen, setSidebarOpen] = useState(false);
   const { user, logout } = useAuth();
   const location = useLocation();
   const navigate = useNavigate();
 
   const handleLogout = () => {
     logout();
     navigate('/login');
   };
 
   return (
     <div className="flex min-h-screen w-full">
       {/* Mobile sidebar backdrop */}
       {sidebarOpen && (
         <div
           className="fixed inset-0 z-40 bg-foreground/20 backdrop-blur-sm lg:hidden"
           onClick={() => setSidebarOpen(false)}
         />
       )}
 
       {/* Sidebar */}
       <aside
         className={cn(
           'fixed inset-y-0 left-0 z-50 w-64 transform bg-sidebar text-sidebar-foreground transition-transform duration-200 ease-in-out lg:relative lg:translate-x-0',
           sidebarOpen ? 'translate-x-0' : '-translate-x-full'
         )}
       >
         <div className="flex h-full flex-col">
           {/* Logo */}
           <div className="flex h-16 items-center gap-3 border-b border-sidebar-border px-6">
             <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sidebar-primary">
               <Building2 className="h-5 w-5 text-sidebar-primary-foreground" />
             </div>
             <div>
               <h1 className="font-semibold text-sidebar-foreground">a_toggle</h1>
               <p className="text-xs text-sidebar-foreground/70">Real Estate</p>
             </div>
             <button
               className="ml-auto lg:hidden"
               onClick={() => setSidebarOpen(false)}
             >
               <X className="h-5 w-5" />
             </button>
           </div>
 
           {/* Navigation */}
           <nav className="flex-1 space-y-1 px-3 py-4">
             {navItems.map((item) => {
               const isActive = location.pathname === item.href || 
                 (item.href !== '/dashboard' && location.pathname.startsWith(item.href));
               return (
                 <Link
                   key={item.href}
                   to={item.href}
                   onClick={() => setSidebarOpen(false)}
                   className={cn(
                     'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                     isActive
                       ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                       : 'text-sidebar-foreground/80 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground'
                   )}
                 >
                   <item.icon className="h-5 w-5" />
                   {item.name}
                 </Link>
               );
             })}
           </nav>
 
           {/* User section */}
           <div className="border-t border-sidebar-border p-3">
             <DropdownMenu>
               <DropdownMenuTrigger asChild>
                 <button className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm hover:bg-sidebar-accent/50 transition-colors">
                   <div className="flex h-8 w-8 items-center justify-center rounded-full bg-sidebar-accent">
                     <User className="h-4 w-4" />
                   </div>
                   <div className="flex-1 text-left">
                     <p className="font-medium text-sidebar-foreground truncate">
                       {user?.full_name || user?.email?.split('@')[0] || 'User'}
                     </p>
                     <p className="text-xs text-sidebar-foreground/70 truncate">
                       {user?.email}
                     </p>
                   </div>
                   <ChevronDown className="h-4 w-4 text-sidebar-foreground/70" />
                 </button>
               </DropdownMenuTrigger>
               <DropdownMenuContent align="end" className="w-56">
                 <DropdownMenuLabel>My Account</DropdownMenuLabel>
                 <DropdownMenuSeparator />
                 <DropdownMenuItem onClick={handleLogout}>
                   <LogOut className="mr-2 h-4 w-4" />
                   Log out
                 </DropdownMenuItem>
               </DropdownMenuContent>
             </DropdownMenu>
           </div>
         </div>
       </aside>
 
       {/* Main content */}
       <div className="flex flex-1 flex-col">
         {/* Top bar */}
         <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b bg-background px-4 lg:px-6">
           <Button
             variant="ghost"
             size="icon"
             className="lg:hidden"
             onClick={() => setSidebarOpen(true)}
           >
             <Menu className="h-5 w-5" />
           </Button>
           <div className="flex-1" />
         </header>
 
         {/* Page content */}
         <main className="flex-1 p-4 lg:p-6">{children}</main>
       </div>
     </div>
   );
 }