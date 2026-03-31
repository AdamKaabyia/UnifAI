import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AnalyticCard } from "./AnalyticCard";
import { Pagination } from "@/components/shared/Pagination";

interface AllUsersTableProps {
  users: Array<{
    user_id: string;
    run_count: number;
    blueprints_used: number;
  }>;
  page: number;
  setPage: (updater: (page: number) => number) => void;
  itemsPerPage: number;
}

export function AllUsersTable({ users, page, setPage, itemsPerPage }: AllUsersTableProps) {
  const pageCount = Math.ceil(users.length / itemsPerPage);

  return (
    <AnalyticCard title="User Activity Summary">
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>User ID</TableHead>
              <TableHead className="text-right">Runs</TableHead>
              <TableHead className="text-right">Blueprints</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.length > 0 ? (
              users.slice(page * itemsPerPage, (page + 1) * itemsPerPage).map((user, idx) => (
                <TableRow key={idx} className="hover:bg-muted/50">
                  <TableCell className="font-medium text-sm truncate max-w-[200px]">
                    {user.user_id}
                  </TableCell>
                  <TableCell className="text-right text-sm">{user.run_count}</TableCell>
                  <TableCell className="text-right text-sm">{user.blueprints_used}</TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={3} className="text-center py-6 text-gray-400">
                  No user activity data available
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      {users.length > itemsPerPage && (
        <Pagination
          pageIndex={page}
          pageCount={pageCount}
          pageSize={itemsPerPage}
          totalItems={users.length}
          onPreviousPage={() => setPage((p) => Math.max(0, p - 1))}
          onNextPage={() => setPage((p) => p + 1)}
          canPreviousPage={page > 0}
          canNextPage={page < pageCount - 1}
          itemName="users"
        />
      )}
    </AnalyticCard>
  );
}
