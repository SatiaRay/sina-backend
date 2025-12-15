<?php

namespace App\Http\Middleware;

use App\Services\Tenant\CurrentTenant;
use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class ResolveTenantScope
{
    /**
     * Handle an incoming request.
     *
     * @param  \Closure(\Illuminate\Http\Request): (\Symfony\Component\HttpFoundation\Response)  $next
     */
    public function handle(Request $request, Closure $next): Response
    {
        if (auth('api')->check()) {
            $user = auth('api')->user();

            // Decide workspace IDs (your logic here)
            $workspaceIds = $this->resolveWorkspaceIds($user, $request);

            if (empty($workspaceIds)) {
                abort(403, 'No accessible workspace');
            }

            CurrentTenant::set($workspaceIds);
        }

        return $next($request);
    }

    /**
     * Exttract workspace id form header or returns its primary_workspace_id
     * @param mixed $user
     * @param mixed $request
     */
    private function resolveWorkspaceIds($user, $request)
    {
        
        // Priority 1: Explicit header (e.g. from API clients or mobile apps)
        if ($request->hasHeader('X-Workspace-Id')) {
            $id = $request->header('X-Workspace-Id');
            
            if ($user->workspaces()->where('id', $id)->exists()) {
                return [$id];
            }
            
            // Optional: you could abort(403) here if invalid header is sent
            // But for flexibility, fall through to next options
        }
        
        // Priority 2: Query parameter (useful for testing or web routes)
        if ($request->query('workspace_id')) {
            $id = $request->query('workspace_id');
            
            if ($user->workspaces()->where('id', $id)->exists()) {
                return [$id];
            }
        }
        
        // Priority 3: Session (perfect for web dashboard – persists user's choice)
        if (session()->has('current_workspace_id')) {
            $id = session('current_workspace_id');

            if ($user->workspaces()->where('id', $id)->exists()) {
                return [$id];
            }

            // Invalid/stale session value – clear it
            session()->forget('current_workspace_id');
        }
        
        // Priority 4: User's primary workspace (safe default)
        if ($user->primary_workspace_id) {
            // Optional: auto-save to session for consistency
            session(['current_workspace_id' => $user->primary_workspace_id]);
            
            return [$user->primary_workspace_id];
        }
        
        // Priority 5: All workspaces the user belongs to
        // (Use with caution – can be many, but safe fallback)
        $allWorkspaceIds = $user->workspaces()->pluck('workspaces.id')->toArray();
        
        if (!empty($allWorkspaceIds)) {
            // Optionally set the first one as current in session
            session(['current_workspace_id' => $allWorkspaceIds[0]]);
            
            return $allWorkspaceIds;
        }

        // Final fallback: no access
        return [];
    }
}
