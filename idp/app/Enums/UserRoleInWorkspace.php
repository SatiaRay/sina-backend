<?php

namespace App\Enums;

enum UserRoleInWorkspace: string
{
    case OWNER = 'owner';
    case MEMBER = 'member';
    case GUEST = 'guest';
}
