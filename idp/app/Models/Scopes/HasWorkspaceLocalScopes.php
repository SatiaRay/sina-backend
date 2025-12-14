<?php

namespace App\Models\Scopes;

use App\Services\Tenant\CurrentTenant;
use Illuminate\Database\Eloquent\Builder;

trait HasWorkspaceLocalScopes
{
    /**
     * Scope queries to the current tenant's workspace(s).
     */
    public function scopeInUserWorkspaces(Builder $query): Builder
    {
        $workspaceIds = CurrentTenant::ids();

        if (empty($workspaceIds)) {
            return $query->whereRaw('false'); // no access
        }

        // For the Workspace model itself
        if ($this->getTable() === 'workspaces') {
            return $query->whereIn('id', $workspaceIds);
        }

        // For models that have workspace_id column (Project, AuditLog, etc.)
        if (in_array('workspace_id', $this->getFillable()) ||
            $query->getModel()->getConnection()->getSchemaBuilder()->hasColumn($this->getTable(), 'workspace_id')) {
            return $query->whereIn('workspace_id', $workspaceIds);
        }

        // Fallback – do nothing if not applicable
        return $query;
    }

    /**
     * Optional: Scope users to those belonging to current workspace(s)
     */
    public function scopeInCurrentTenantWorkspaces(Builder $query): Builder
    {
        $workspaceIds = CurrentTenant::ids();

        if (empty($workspaceIds)) {
            return $query->whereRaw('false');
        }

        return $query->whereHas('workspaces', function (Builder $q) use ($workspaceIds) {
            $q->whereIn('workspaces.id', $workspaceIds);
        });
    }
}