// ============================================================
// Admin Users Management - Candway
// Real data from /admin/users API
// ============================================================

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Input } from '@/shared/components/ui/input';
import { Avatar } from '@/shared/components/ui/avatar';
import { SimpleDropdown } from '@/shared/components/ui/dropdown-menu';
import { customToast } from '@/shared/components/ui/toast';
import { Search, Filter, MoreHorizontal, ShieldAlert, UserX, UserCheck, Shield, RefreshCw } from 'lucide-react';
import { adminService } from '@/services/admin.service';

interface AdminUser {
  id: number;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  joined?: string;
  tier?: string;
}

function getRoleVariant(role: string) {
  const map: Record<string, 'warning' | 'primary' | 'info' | 'success' | 'default'> = {
    admin: 'warning',
    recruiter: 'primary',
    mentor: 'info',
    candidate: 'success',
  };
  return map[role] || 'default';
}

export default function UsersManagementPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  void setPage;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminService.getUsers({ search, page, per_page: 50 });
      setUsers(data.users);
      setTotal(data.total);
    } catch (err) {
      console.error('Users load error:', err);
      customToast({ type: 'error', title: 'Users', message: 'Failed to load users.' });
    } finally {
      setLoading(false);
    }
  }, [search, page]);

  useEffect(() => { load(); }, [load]);

  const toggleStatus = async (id: number, current: boolean) => {
    try {
      if (current) {
        await adminService.suspendUser(String(id), 'Suspended via admin panel');
      } else {
        await adminService.activateUser(String(id));
      }
      setUsers(u => u.map(x => x.id === id ? { ...x, is_active: !current } : x));
      customToast({ type: current ? 'warning' : 'success', title: `User ${current ? 'Suspended' : 'Activated'}`, message: 'User account status updated.' });
    } catch (err: any) {
      customToast({ type: 'error', title: 'Action Failed', message: err?.message || 'Could not update user.' });
    }
  };

  const filtered = users.filter(u => {
    const q = search.toLowerCase();
    return u.email.toLowerCase().includes(q) || u.name.toLowerCase().includes(q);
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Users & Roles</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Manage all registered accounts and their RBAC permissions.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={load}>
            Refresh
          </Button>
          <Button variant="primary" leftIcon={<Shield className="h-4 w-4" />} onClick={() => customToast({ type: 'info', title: 'Invite Admin', message: 'Admin invitation is handled via email.' })}>
            Invite Admin
          </Button>
        </div>
      </div>

      <Card className="glass-panel border-purple-200/50 dark:border-purple-500/20">
        <CardHeader>
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div>
              <CardTitle>User Directory</CardTitle>
              <CardDescription>Total {total} registered accounts</CardDescription>
            </div>
            <div className="flex items-center gap-2 w-full sm:w-auto">
              <Input
                placeholder="Search email or name..."
                leftIcon={<Search className="h-4 w-4" />}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                wrapperClassName="w-full sm:w-64"
              />
              <Button variant="outline" leftIcon={<Filter className="h-4 w-4" />}>Filter</Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
              <span className="text-sm text-gray-500">Loading users...</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-purple-100 dark:border-white/10">
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase tracking-wider">User</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase tracking-wider">Role</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase tracking-wider">Joined</th>
                    <th className="py-3 text-xs font-bold text-gray-500 uppercase tracking-wider text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((user) => (
                    <tr key={user.id} className="border-b border-gray-50 dark:border-white/[0.02] hover:bg-purple-50/50 dark:hover:bg-white/[0.02] transition-colors">
                      <td className="py-3">
                        <div className="flex items-center gap-3">
                          <Avatar name={user.name} size="sm" />
                          <div>
                            <div className="font-bold text-sm text-gray-900 dark:text-white">{user.name}</div>
                            <div className="text-xs text-gray-500">{user.email}</div>
                          </div>
                        </div>
                      </td>
                      <td className="py-3">
                        <Badge variant={getRoleVariant(user.role)} size="sm" className="uppercase text-[10px] font-bold">
                          {user.role}
                        </Badge>
                      </td>
                      <td className="py-3">
                        <Badge variant={user.is_active ? 'success' : 'danger'} size="sm" dot>
                          {user.is_active ? 'active' : 'suspended'}
                        </Badge>
                      </td>
                      <td className="py-3 text-sm text-gray-500 font-medium">
                        {user.joined || '—'}
                      </td>
                      <td className="py-3 text-right">
                        <SimpleDropdown
                          trigger={
                            <button className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-white/10 transition-colors">
                              <MoreHorizontal className="h-4 w-4 text-gray-500" />
                            </button>
                          }
                          items={[
                            {
                              label: 'Edit Permissions',
                              icon: <ShieldAlert className="h-4 w-4 text-amber-500" />,
                              onClick: () => customToast({ type: 'info', title: 'Permissions', message: 'Opening permissions manager...' }),
                            },
                            {
                              label: user.is_active ? 'Suspend User' : 'Activate User',
                              icon: user.is_active ? <UserX className="h-4 w-4" /> : <UserCheck className="h-4 w-4" />,
                              danger: user.is_active,
                              onClick: () => toggleStatus(user.id, user.is_active),
                            },
                          ]}
                          align="end"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filtered.length === 0 && !loading && (
                <div className="text-center py-10 text-sm text-gray-500">No users match your search.</div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
