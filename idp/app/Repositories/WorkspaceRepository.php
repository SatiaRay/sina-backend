<?php
namespace App\Repositories;

use App\Models\Workspace;

class WorkspaceRepository
{
	 /**
     * @var Workspace
     */
    protected Workspace $workspace;

    /**
     * Workspace constructor.
     *
     * @param Workspace $workspace
     */
    public function __construct(Workspace $workspace)
    {
        $this->workspace = $workspace;
    }

    /**
     * Get all workspace.
     *
     * @return Workspace $workspace
     */
    public function all()
    {
        return $this->workspace->inUserWorkspaces()->get();
    }

     /**
     * Get workspace by id
     *
     * @param $id
     * @return mixed
     */
    public function getById(string $id)
    {
        return $this->workspace->find($id);
    }

    /**
     * Save Workspace
     *
     * @param $data
     * @return Workspace
     */
     public function save(array $data): Workspace
    {
        return Workspace::create($data);
    }

     /**
     * Update Workspace
     *
     * @param $data
     * @return Workspace
     */
    public function update(array $data, string $id)
    {
        $workspace = $this->workspace->find($id);
        $workspace->update($data);
        return $workspace;
    }

    /**
     * Delete Workspace
     *
     * @param $data
     * @return Workspace
     */
   	 public function delete(string $id)
    {
        $workspace = $this->workspace->find($id);
        $workspace->delete();
        return $workspace;
    }
}
