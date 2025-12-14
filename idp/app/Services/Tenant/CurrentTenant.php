<?php

namespace App\Services\Tenant;

class CurrentTenant
{
    protected static array $workspaceIds = [];

    public static function set(array $ids): void { static::$workspaceIds = $ids; }
    public static function ids(): array { return static::$workspaceIds; }
    public static function clear(): void { static::$workspaceIds = []; }
}