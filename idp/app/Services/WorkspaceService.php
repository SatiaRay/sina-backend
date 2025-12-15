<?php
namespace App\Services;

use App\Models\Workspace;
use App\Repositories\WorkspaceRepository;
use Exception;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;

class WorkspaceService
{
	/**
     * @var WorkspaceRepository $workspaceRepository
     */
    protected $workspaceRepository;

    /**
     * DummyClass constructor.
     *
     * @param WorkspaceRepository $workspaceRepository
     */
    public function __construct(WorkspaceRepository $workspaceRepository)
    {
        $this->workspaceRepository = $workspaceRepository;
    }

    /**
     * Get all workspaceRepository.
     *
     * @return String
     */
    public function getAll()
    {
        return $this->workspaceRepository->all();
    }

    /**
     * Get workspaceRepository by id.
     *
     * @param $id
     * @return String
     */
    public function getById(string $id)
    {
        return $this->workspaceRepository->getById($id);
    }

    /**
     * Validate workspaceRepository data.
     * Store to DB if there are no errors.
     *
     * @param array $data
     * @return String
     */
    public function save(array $data): Workspace
    {
        return $this->workspaceRepository->save($data);
    }

    /**
     * Update workspaceRepository data
     * Store to DB if there are no errors.
     *
     * @param array $data
     * @return String
     */
    public function update(array $data, string $id)
    {
        DB::beginTransaction();
        try {
            $workspaceRepository = $this->workspaceRepository->update($data, $id);
            DB::commit();
            return $workspaceRepository;
        } catch (Exception $e) {
            DB::rollBack();
            report($e);
            throw new InvalidArgumentException('Unable to update post data');
        }
    }

    /**
     * Delete workspaceRepository by id.
     *
     * @param $id
     * @return String
     */
    public function deleteById(string $id)
    {
        DB::beginTransaction();
        try {
            $workspaceRepository = $this->workspaceRepository->delete($id);
            DB::commit();
            return $workspaceRepository;
        } catch (Exception $e) {
            DB::rollBack();
            report($e);
            throw new InvalidArgumentException('Unable to delete post data');
        }
    }

}
