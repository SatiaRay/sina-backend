<?php

namespace App\Http\Controllers\API;

use App\Http\Controllers\Controller;
use App\Http\Requests\WorkspaceRequest;
use App\Http\Resources\WorkspaceResource;
use App\Services\WorkspaceService;
use Illuminate\Http\Request;
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
            return new WorkspaceResource($this->workspaceService->save($request->validated()));
        } catch (\Exception $exception) {
            report($exception);
            return response()->json(['error' => 'There is an error.'], Response::HTTP_INTERNAL_SERVER_ERROR);
        }
    }

    public function show(string $id): WorkspaceResource
    {
        return WorkspaceResource::make($this->workspaceService->getById($id));
    }

    public function update(WorkspaceRequest $request, string $id): WorkspaceResource|\Illuminate\Http\JsonResponse
    {
        try {
            return new WorkspaceResource($this->workspaceService->update($request->validated(), $id));
        } catch (\Exception $exception) {
            report($exception);
            return response()->json(['error' => 'There is an error.'], Response::HTTP_INTERNAL_SERVER_ERROR);
        }
    }

    public function destroy(string $id): \Illuminate\Http\JsonResponse
    {
        try {
            $this->workspaceService->deleteById($id);
            return response()->json(['message' => 'Deleted successfully'], Response::HTTP_OK);
        } catch (\Exception $exception) {
            report($exception);
            return response()->json(['error' => 'There is an error.'], Response::HTTP_INTERNAL_SERVER_ERROR);
        }
    }
}
