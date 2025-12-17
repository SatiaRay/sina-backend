<?php

namespace App\Services\Tenant;

class CurrentWorkspace
{
    protected static string|null $workspaceId = null;

    public static function set(string $id): void { static::$workspaceId = $id; }
    public static function id(): string|null { return static::$workspaceId; }
    public static function clear(): void { static::$workspaceId = null; }
}