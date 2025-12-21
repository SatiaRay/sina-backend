<?php

namespace App\Http\Controllers\API;

use App\Models\Workspace;
use Illuminate\Http\Request;
use App\Services\UserService;
use App\Http\Requests\UserRequest;
use App\Services\WorkspaceService;
use App\Http\Controllers\Controller;
use App\Http\Resources\UserResource;
use App\Http\Resources\WorkspaceResource;
use Symfony\Component\HttpFoundation\Response;

class UserController extends Controller
{
    /**
     * DummyModel Constructor
     *
     * @param UserService $userService
     *
     */
    public function __construct(
        protected UserService $userService,
        protected WorkspaceService $workspaceService
    ) {
        //
    }

    /**
     * Get all workspaces the authenticated user belongs to
     *
     * @return void
     */
    public function getUserWorkspaces(): \Illuminate\Http\Resources\Json\AnonymousResourceCollection
    {
        return WorkspaceResource::collection($this->workspaceService->getAll());
    }

    /**
     * Switch current active workspace
     * 
     * @param mixed $workspaceId
     * @return \Illuminate\Http\JsonResponse
     */
    public function switchWorkspace($workspaceId)
    {
        $workspace = Workspace::inUserWorkspaces()->findOrFail($workspaceId);

        // Store active workspace in session or token
        session(['current_workspace_id' => $workspaceId]);

        return response()->json([
            'message' => 'Workspace switched successfully',
            'workspace' => $workspace,
        ]);
    }
}
