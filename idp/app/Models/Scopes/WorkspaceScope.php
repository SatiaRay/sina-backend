<?php

namespace App\Models\Scopes;

use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Scope;
use Illuminate\Support\Facades\Auth;

class WorkspaceScope implements Scope
{
    /**
     * Apply the scope to a given Eloquent query builder.
     */
    public function apply(Builder $builder, Model $model): void
    {
        if (!Auth::check()) {
            // Optionally abort or allow nothing
            $builder->whereRaw('1 = 0');
            return;
        }

        $workspaceIds = $this->getCurrentWorkspaceIds();

        if (empty($workspaceIds)) {
            $builder->whereRaw('1 = 0');
            return;
        }
        // Models that have workspace_id column directly
        if (in_array('workspace_id', $model->getFillable()) || $model->getTable() === 'workspaces') {
            if ($model->getTable() === 'workspaces') {
                $builder->whereIn('id', $workspaceIds);
            } else {
                $builder->whereIn('workspace_id', $workspaceIds);
            }
        }

        // Special case: User model – restrict to users in these workspaces
        if ($model instanceof \App\Models\User) {
            $builder->whereHas('workspaces', function (Builder $q) use ($workspaceIds) {
                $q->whereIn('workspaces.id', $workspaceIds);
            });
        }
    }

    /**
     * Get the workspace IDs the current user can access.
     * You can customize this logic (e.g. include primary_workspace_id fallback).
     */
    protected function getCurrentWorkspaceIds(): array
    {
        /** @var \App\Models\User $user */
        $user = auth('api')->user();

        // Option 1: Use a "current workspace" stored in session or request
        // Useful when your frontend selects a workspace
        if (session()->has('current_workspace_id')) {
            $wid = session('current_workspace_id');
            // Verify the user actually belongs to it
            if ($user->workspaces()->where('workspaces.id', $wid)->exists()) {
                return [$wid];
            }
        }

        // Option 2: Use primary_workspace_id as fallback
        if ($user->primary_workspace_id) {
            return [$user->primary_workspace_id];
        }

        // Option 3: Return all workspaces the user belongs to
        return $user->workspaces()->pluck('workspaces.id')->toArray();
    }
}