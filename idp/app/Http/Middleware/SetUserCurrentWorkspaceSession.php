<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class SetUserCurrentWorkspaceSession
{
    /**
     * Handle an incoming request.
     *
     * @param  \Closure(\Illuminate\Http\Request): (\Symfony\Component\HttpFoundation\Response)  $next
     */
    public function handle(Request $request, Closure $next): Response
    {
        if (auth()->check() && $request->has('workspace_id')) {
            $workspaceId = $request->input('workspace_id');

            if (auth()->user()->workspaces()->where('id', $workspaceId)->exists()) {
                session(['current_workspace_id' => $workspaceId]);
            }
        }

        return $next($request);
    }
}
