<?php

namespace App\Models\Scopes;

/**
 * Workspace scope trait
 */
trait HasWorkspaceGlobalScope
{
    protected static function bootHasWorkspaceGlobalScope(): void
    {
        static::addGlobalScope(new WorkspaceGlobalScope);
    }
}