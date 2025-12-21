<?php

namespace App\Http\Controllers\API;

use App\Models\User;
use App\Models\Workspace;
use Illuminate\Http\Request;
use App\Enums\UserRoleInWorkspace;
use App\Services\WorkspaceService;
use Illuminate\Support\Facades\DB;
use App\Http\Controllers\Controller;
use App\Http\Resources\UserResource;
use App\Http\Requests\WorkspaceRequest;
use App\Http\Resources\WorkspaceResource;
use App\Http\Requests\WorkspaceInviteRequest;
use App\Http\Resources\WorkspaceMembershipResource;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Response;

class WorkspaceController extends Controller
{
    /**
     * @var WorkspaceService
     */
    protected WorkspaceService $workspaceService;

    /**
     * DummyModel Constructor
     *
     * @param WorkspaceService $workspaceService
     *
     */
    public function __construct(WorkspaceService $workspaceService)
    {
        $this->workspaceService = $workspaceService;
    }

    public function index(): \Illuminate\Http\Resources\Json\AnonymousResourceCollection
    {
        return WorkspaceResource::collection($this->workspaceService->getAll());
    }

    public function store(WorkspaceRequest $request): WorkspaceResource|\Illuminate\Http\JsonResponse
    {
        try {
            DB::beginTransaction();

            $workspace = $this->workspaceService->save($request->validated());

            auth()->user()->workspaces()->attach($workspace->id, ['role' => UserRoleInWorkspace::OWNER->value]);

            DB::commit();

            return new WorkspaceResource($workspace);
        } catch (\Exception $exception) {
            report($exception);
            return response()->json(['error' => 'There is an error.'], Response::HTTP_INTERNAL_SERVER_ERROR);
        }
    }

    public function show(string $id): \Illuminate\Http\JsonResponse
    {
        $workspace = Workspace::inUserWorkspaces()->findOrFail($id);

        return response()->json([
            "workspace" => new WorkspaceResource($this->workspaceService->getById($workspace->id)),
            // "members" => UserResource::collection($workspace->users),
            "members" => WorkspaceMembershipResource::collection($workspace->users),
        ]);
    }

    public function update(WorkspaceRequest $request, string $id): WorkspaceResource|\Illuminate\Http\JsonResponse
    {
        $user = auth()->user();

        // Check if user can invite (owners and maybe admins)
        $membership = $user->workspaces()
            ->where('workspace_id', $id)
            ->first();

        if (!$membership || !in_array($membership->pivot->role, ['owner'])) {
            return response()->json([
                'error' => 'Only workspace owners can update workspace settings'
            ], Response::HTTP_FORBIDDEN);
        }

        try {
            return new WorkspaceResource($this->workspaceService->update($request->validated(), $id));
        } catch (\Exception $exception) {
            report($exception);
            return response()->json(['error' => 'There is an error.'], Response::HTTP_INTERNAL_SERVER_ERROR);
        }
    }

    public function destroy(string $id): \Illuminate\Http\JsonResponse
    {
        $user = auth()->user();

        // Check if user can invite (owners and maybe admins)
        $membership = $user->workspaces()
            ->where('workspace_id', $id)
            ->first();

        if (!$membership || !in_array($membership->pivot->role, ['owner'])) {
            return response()->json([
                'error' => 'Only workspace owners can delete the workspace'
            ], Response::HTTP_FORBIDDEN);
        }

        try {
            $this->workspaceService->deleteById($id);
            return response()->json(['message' => 'Deleted successfully'], Response::HTTP_OK);
        } catch (\Exception $exception) {
            report($exception);
            return response()->json(['error' => 'There is an error.'], Response::HTTP_INTERNAL_SERVER_ERROR);
        }
    }

    /**
     * Invite user to workspace
     *
     * @param WorkspaceInviteRequest $request
     * @param int $workspaceId
     * @return \Illuminate\Http\JsonResponse
     */
    public function invite(WorkspaceInviteRequest $request, $workspaceId)
    {
        $user = auth()->user();
        $workspace = Workspace::findOrFail($workspaceId);

        // Check if user can invite (owners and maybe admins)
        $membership = $user->workspaces()
            ->where('workspace_id', $workspaceId)
            ->first();

        if (!$membership || !in_array($membership->pivot->role, ['owner'])) {
            return response()->json([
                'error' => 'You do not have permission to invite users'
            ], Response::HTTP_FORBIDDEN);
        }

        // Find or create user by email
        $invitedUser = User::where('email', $request->email)->first();

        if (!$invitedUser) {
            // In a real app, you might send an email invitation
            // For MVP, we'll just return an error
            return response()->json([
                'error' => 'User not found. They need to register first.'
            ], Response::HTTP_NOT_FOUND);
        }

        // Check if user is already a member
        if ($invitedUser->workspaces()->where('workspace_id', $workspaceId)->exists()) {
            return response()->json([
                'error' => 'User is already a member of this workspace'
            ], Response::HTTP_CONFLICT);
        }

        // Add user to workspace
        $invitedUser->workspaces()->attach($workspaceId, [
            'role' => $request->role ?? 'member'
        ]);

        return response()->json([
            'message' => 'User invited successfully',
            'user' => new UserResource($invitedUser)
        ], Response::HTTP_CREATED);
    }

    /**
     * Remove member from workspace
     *
     * @param Request $request
     * @param int $workspaceId
     * @param int $userId
     * @return \Illuminate\Http\JsonResponse
     */
    public function removeMember($workspaceId, $userId)
    {
        $user = auth()->user();
        $workspace = Workspace::findOrFail($workspaceId);

        // Check if user is owner
        $membership = $user->workspaces()
            ->where('workspace_id', $workspaceId)
            ->first();

        if (!$membership || $membership->pivot->role !== 'owner') {
            return response()->json([
                'error' => 'Only workspace owners can remove members'
            ], Response::HTTP_FORBIDDEN);
        }

        // Cannot remove yourself
        if ($user->id == $userId) {
            return response()->json([
                'error' => 'Cannot remove yourself from workspace'
            ], Response::HTTP_FORBIDDEN);
        }

        // Remove user from workspace
        $workspace->users()->detach($userId);

        return response()->json([
            'message' => 'Member removed successfully'
        ]);
    }

    /**
     * Leave workspace
     *
     * @param int $workspaceId
     * @return \Illuminate\Http\JsonResponse
     */
    public function leave($workspaceId)
    {
        $user = auth()->user();
        $workspace = Workspace::findOrFail($workspaceId);

        // Check if user is a member
        if (!$user->workspaces()->where('workspace_id', $workspaceId)->exists()) {
            return response()->json([
                'error' => 'You are not a member of this workspace'
            ], Response::HTTP_FORBIDDEN);
        }

        // Check if user is the owner (owners cannot leave, must transfer ownership or delete)
        $membership = $user->workspaces()
            ->where('workspace_id', $workspaceId)
            ->first();

        if ($membership->pivot->role === 'owner') {
            return response()->json([
                'error' => 'Workspace owner cannot leave. Transfer ownership or delete workspace.'
            ], Response::HTTP_FORBIDDEN);
        }

        // Remove user from workspace
        $user->workspaces()->detach($workspaceId);

        // Clear session if this was the current workspace
        if (session('current_workspace_id') == $workspaceId) {
            session()->forget('current_workspace_id');
        }

        return response()->json([
            'message' => 'You have left the workspace'
        ]);
    }
}
