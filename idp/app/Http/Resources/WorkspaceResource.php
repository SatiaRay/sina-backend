<?php

namespace App\Http\Resources;

use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

class WorkspaceResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        return [
            "id" => $this->id,
            'name' => $this->name,
            'plan' => $this->plan,
            'metadata' => $this->metadata,
            'deleted_at' => $this->deleted_at,
        ];
    }
}
