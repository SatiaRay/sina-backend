<?php

namespace App\Models\Scopes;

/**
 * Workspace scope trait
 */
trait HasWorkspaceScope
{
    protected static function bootHasWorkspaceScope(): void
    {
        static::addGlobalScope(new WorkspaceScope);
    }
}