// import { Property } from '@/lib/api';

// export function getMonthlyData(properties: Property[]) {
//   const months = Array.from({ length: 12 }, (_, i) => {
//     const d = new Date();
//     d.setMonth(i);
//     return { month: d.toLocaleString('default', { month: 'short' }), index: i };
//   });

//   return months.map(({ month, index }) => {
//     const sold = properties.filter(p => {
//       if (!p.is_sold) return false;
//       const d = new Date(p.updated_at);
//       return d.getMonth() === index && d.getFullYear() === new Date().getFullYear();
//     });
//     return {
//       month,
//       sold: sold.length,
//       revenue: sold.reduce((s, p) => s + (p.price || 0), 0),
//     };
//   });
// }

// export function getPropertyTypeStats(properties: Property[]) {
//   const types: Record<string, number> = {};
//   properties.filter(p => !p.is_deleted).forEach(p => {
//     const t = p.property_type || 'Other';
//     types[t] = (types[t] || 0) + 1;
//   });
//   const colors: Record<string, string> = {
//     apartment: '#00D4FF', Apartment: '#00D4FF',
//     villa: '#F5C518', Villa: '#F5C518',
//     plot: '#22C55E', Plot: '#22C55E', Land: '#22C55E',
//     commercial: '#FF6B35', Commercial: '#FF6B35',
//     farmhouse: '#A855F7', Farmhouse: '#A855F7',
//     House: '#00D4FF', Condo: '#EC4899', Townhouse: '#F5C518',
//     other: '#EC4899', Other: '#EC4899',
//   };
//   return Object.entries(types).map(([name, value]) => ({
//     name,
//     value,
//     color: colors[name] || '#8B8FA8',
//   }));
// }

// export function getSoldInPeriod(properties: Property[], days: number) {
//   const now = new Date();
//   const cutoff = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
//   return properties.filter(p => p.is_sold && new Date(p.updated_at) >= cutoff).length;
// }

// export function formatCurrency(value: number): string {
//   if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
//   if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
//   return `$${value.toLocaleString()}`;
// }


import { Property } from '@/lib/api';

export function getMonthlyData(properties: Property[]) {
  const months = Array.from({ length: 12 }, (_, i) => {
    const d = new Date();
    d.setMonth(i);
    return { month: d.toLocaleString('default', { month: 'short' }), index: i };
  });

  return months.map(({ month, index }) => {
    const sold = properties.filter(p => {
      if (p.status !== 'sold') return false;
      const d = new Date(p.updated_at);
      return d.getMonth() === index && d.getFullYear() === new Date().getFullYear();
    });
    return {
      month,
      sold: sold.length,
      revenue: sold.reduce((s, p) => s + (p.price || 0), 0),
    };
  });
}

export function getPropertyTypeStats(properties: Property[]) {
  const types: Record<string, number> = {};
  properties.filter(p => p.status !== 'inactive').forEach(p => {
    const t = p.property_type || 'Other';
    types[t] = (types[t] || 0) + 1;
  });
  const colors: Record<string, string> = {
    apartment: '#00D4FF',
    villa: '#F5C518',
    plot: '#22C55E',
    commercial: '#FF6B35',
    farmhouse: '#A855F7',
    other: '#EC4899',
  };
  return Object.entries(types).map(([name, value]) => ({
    name,
    value,
    color: colors[name.toLowerCase()] || '#8B8FA8',
  }));
}

export function getSoldInPeriod(properties: Property[], days: number) {
  const now = new Date();
  const cutoff = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
  return properties.filter(p => p.status === 'sold' && new Date(p.updated_at) >= cutoff).length;
}

export function formatCurrency(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toLocaleString()}`;
}