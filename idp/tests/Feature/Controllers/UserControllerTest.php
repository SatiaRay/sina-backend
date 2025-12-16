<?php

namespace Tests\Feature\API;

use App\Models\User;
use App\Models\Workspace;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Foundation\Testing\WithFaker;
use Illuminate\Support\Facades\Session;
use Tests\TestCase;

class UserControllerTest extends TestCase
{
    use RefreshDatabase, WithFaker;

    /**
     * @var User
     */
    protected $user;

    /**
     * @var Workspace
     */
    protected $workspace;

    /**
     * @var Workspace
     */
    protected $otherWorkspace;

    /**
     * Set up the test
     */
    protected function setUp(): void
    {
        parent::setUp();

        // Create a test user
        $this->user = User::factory()->create([
            'email' => 'test@example.com',
            'password' => bcrypt('password123')
        ]);

        // Create a workspace WITHOUT owner_id
        $this->workspace = Workspace::factory()->create([
            'name' => 'Test Workspace',
            // Remove owner_id from here
        ]);

        // Attach user to workspace as OWNER
        $this->user->workspaces()->attach($this->workspace->id, [
            'role' => 'owner' // Using enum value or string
        ]);

        // Create another workspace that user does NOT belong to
        $this->otherWorkspace = Workspace::factory()->create([
            'name' => 'Other Workspace',
        ]);

        // Create another user and attach them as owner of other workspace
        $otherUser = User::factory()->create();
        $otherUser->workspaces()->attach($this->otherWorkspace->id, [
            'role' => 'owner'
        ]);
    }

    
    public function test_authenticated_user_can_get_their_workspaces()
    {
        // Act as the authenticated user
        $this->actingAs($this->user, 'api');

        // Make the API request
        $response = $this->getJson('/api/me/workspaces');

        // Assert response status
        $response->assertStatus(200);

        // Assert response structure
        $response->assertJsonStructure([
            'data' => [
                '*' => [
                    'id',
                    'name',
                    'plan',
                    'metadata',
                ]
            ]
        ]);

        // Assert only the user's workspace is returned
        $response->assertJsonCount(1, 'data');
        $response->assertJsonFragment([
            'id' => $this->workspace->id,
            'name' => 'Test Workspace'
        ]);

        // Assert the other workspace is not included
        $response->assertJsonMissing([
            'id' => $this->otherWorkspace->id,
            'name' => 'Other Workspace'
        ]);
    }

    
    public function test_workspace_response_includes_role_through_pivot()
    {
        $this->actingAs($this->user, 'api');

        // If your WorkspaceResource includes pivot data
        $response = $this->getJson('/api/me/workspaces');

        $response->assertStatus(200);

        // Check if pivot data is included (if your resource adds it)
        $data = $response->json('data.0');

        // If you want to include role in response, you might need to:
        // 1. Load pivot in service: $user->workspaces()->withPivot('role')->get()
        // 2. Include it in WorkspaceResource
    }

    
    public function test_user_sees_correct_role_for_each_workspace()
    {
        // Add user to another workspace with different role
        $workspace2 = Workspace::factory()->create(['name' => 'Workspace 2']);
        $this->user->workspaces()->attach($workspace2->id, [
            'role' => 'member'
        ]);

        $workspace3 = Workspace::factory()->create(['name' => 'Workspace 3']);
        $this->user->workspaces()->attach($workspace3->id, [
            'role' => 'guest'
        ]);

        $this->actingAs($this->user, 'api');

        $response = $this->getJson('/api/me/workspaces');
        $response->assertStatus(200);
        $response->assertJsonCount(3, 'data');
    }

    
    public function test_authenticated_user_can_switch_to_workspace_they_belong_to()
    {
        $this->actingAs($this->user, 'api');

        $response = $this->postJson("/api/me/workspaces/{$this->workspace->id}/switch");

        $response->assertStatus(200);
        $response->assertJsonStructure([
            'message',
            'workspace' => [
                'id',
                'name',
            ],
        ]);

        $response->assertJson([
            'message' => 'Workspace switched successfully',
            'workspace' => [
                'id' => $this->workspace->id,
                'name' => $this->workspace->name
            ]
        ]);

        // Verify session was updated
        $this->assertEquals($this->workspace->id, session('current_workspace_id'));
    }

    
    public function test_user_cannot_switch_to_workspace_they_dont_belong_to()
    {
        $this->actingAs($this->user, 'api');

        $response = $this->postJson("/api/me/workspaces/{$this->otherWorkspace->id}/switch");

        $response->assertStatus(404);

        // Verify session was not updated
        $this->assertNotEquals(session('current_workspace_id'), $this->otherWorkspace->id);
    }

    
    public function test_cannot_switch_to_nonexistent_workspace()
    {
        $this->actingAs($this->user, 'api');

        $nonExistentId = 999999;
        $response = $this->postJson("/api/me/workspaces/{$nonExistentId}/switch");

        $response->assertStatus(404);
    }

    
    public function test_unauthenticated_user_cannot_switch_workspace()
    {
        $response = $this->postJson("/api/me/workspaces/{$this->workspace->id}/switch");

        $response->assertStatus(401);
    }


    
    public function test_switch_workspace_sets_session_correctly_for_different_roles()
    {
        $this->actingAs($this->user, 'api');

        // User is owner in this workspace
        $this->assertEquals('owner', $this->user->workspaces()
            ->where('workspace_id', $this->workspace->id)
            ->first()->pivot->role);

        // Switch to owner workspace
        $response = $this->postJson("/api/me/workspaces/{$this->workspace->id}/switch");
        $response->assertStatus(200);
        $this->assertEquals($this->workspace->id, session('current_workspace_id'));
    }
}
