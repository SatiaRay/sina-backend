<?php

namespace Tests\Feature\API;

use App\Models\User;
use App\Models\Workspace;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Foundation\Testing\WithFaker;
use Tests\TestCase;

class WorkspaceControllerTest extends TestCase
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
     * @var User
     */
    protected $memberUser;

    /**
     * @var User
     */
    protected $nonMemberUser;


    /**
     * Set up the test
     */
    protected function setUp(): void
    {
        parent::setUp();

        // Create a test user
        $this->user = User::factory()->create([
            'email' => 'owner@example.com',
            'password' => bcrypt('password123')
        ]);

        // Create a workspace
        $this->workspace = Workspace::factory()->create([
            'name' => 'Test Workspace',
        ]);

        // Attach user as owner
        $this->user->workspaces()->attach($this->workspace->id, [
            'role' => 'owner'
        ]);

        // Create another user (member)
        $this->memberUser = User::factory()->create([
            'email' => 'member@example.com'
        ]);
        $this->memberUser->workspaces()->attach($this->workspace->id, [
            'role' => 'member'
        ]);

        // Create another user (non-member)
        $this->nonMemberUser = User::factory()->create([
            'email' => 'nonmember@example.com'
        ]);
    }

    
    public function test_owner_can_create_workspace()
    {
        $this->actingAs($this->user, 'api');

        $data = [
            'name' => 'New Workspace',
            'plan' => 'business',
            'metadata' => json_encode(['color' => '#FF0000']),
        ];

        $response = $this->postJson('/api/workspaces', $data);

        $response->assertStatus(201);
        $response->assertJsonStructure([
            'data' => [
                'id',
                'name',
                'plan',
                'metadata'
            ]
        ]);

        // Verify workspace was created
        $this->assertDatabaseHas('workspaces', [
            'name' => 'New Workspace',
        ]);

        // Verify user is attached as owner
        $workspaceId = $response->json('data.id');
        $this->assertDatabaseHas('user_workspace', [
            'user_id' => $this->user->id,
            'workspace_id' => $workspaceId,
            'role' => 'owner'
        ]);
    }

    
    public function test_workspace_creation_requires_name()
    {
        $this->actingAs($this->user, 'api');

        $response = $this->postJson('/api/workspaces', []);

        $response->assertStatus(422);
        $response->assertJsonValidationErrors(['name']);
    }

    
    public function test_owner_can_view_workspace_details()
    {
        $this->actingAs($this->user, 'api');

        $response = $this->getJson("/api/workspaces/{$this->workspace->id}");

        $response->assertStatus(200);
        $response->assertJsonStructure([
            'workspace' => [
                'id',
                'name',
                'plan',
                'metadata',
            ],
            'members' => [
                '*' => [
                    'id',
                    'name',
                    'email',
                ]
            ]
        ]);
    }

    
    public function test_member_can_view_workspace_details()
    {
        $this->actingAs($this->memberUser, 'api');

        $response = $this->getJson("/api/workspaces/{$this->workspace->id}");

        $response->assertStatus(200);
    }

    
    public function test_non_member_cannot_view_workspace_details()
    {
        $this->actingAs($this->nonMemberUser, 'api');

        $response = $this->getJson("/api/workspaces/{$this->workspace->id}");

        $response->assertStatus(404);
    }

    
    public function test_owner_can_update_workspace()
    {
        $this->actingAs($this->user, 'api');

        $data = [
            'name' => 'Updated Workspace Name',
            'plan' => 'enterprise'
        ];

        $response = $this->putJson("/api/workspaces/{$this->workspace->id}", $data);

        $response->assertStatus(200);
        $response->assertJson([
            'data' => [
                'name' => 'Updated Workspace Name',
                'plan' => 'enterprise'
            ]
        ]);

        $this->assertDatabaseHas('workspaces', [
            'id' => $this->workspace->id,
            'name' => 'Updated Workspace Name'
        ]);
    }

    
    public function test_member_cannot_update_workspace()
    {
        $this->actingAs($this->memberUser, 'api');

        $data = ['name' => 'Try to Update'];

        $response = $this->putJson("/api/workspaces/{$this->workspace->id}", $data);

        $response->assertStatus(403);
        $response->assertJson([
            'error' => 'Only workspace owners can update workspace settings'
        ]);

        // Ensure workspace was not updated
        $this->assertDatabaseHas('workspaces', [
            'id' => $this->workspace->id,
            'name' => 'Test Workspace' // Original name
        ]);
    }

    
    public function test_owner_can_invite_user_to_workspace()
    {
        $this->actingAs($this->user, 'api');

        $newUser = User::factory()->create(['email' => 'newuser@example.com']);

        $data = [
            'email' => 'newuser@example.com',
            'role' => 'member'
        ];

        $response = $this->postJson("/api/workspaces/{$this->workspace->id}/invite", $data);

        $response->assertStatus(201);
        $response->assertJson([
            'message' => 'User invited successfully'
        ]);

        // Verify user was added to workspace
        $this->assertDatabaseHas('user_workspace', [
            'user_id' => $newUser->id,
            'workspace_id' => $this->workspace->id,
            'role' => 'member'
        ]);
    }

    
    public function test_member_cannot_invite_users()
    {
        $this->actingAs($this->memberUser, 'api');

        $data = [
            'email' => 'someuser@example.com',
            'role' => 'member'
        ];

        $response = $this->postJson("/api/workspaces/{$this->workspace->id}/invite", $data);

        $response->assertStatus(403);
        $response->assertJson([
            'error' => 'You do not have permission to invite users'
        ]);
    }

    
    public function test_cannot_invite_existing_member()
    {
        $this->actingAs($this->user, 'api');

        // Try to invite existing member
        $data = [
            'email' => 'member@example.com', // Already a member
            'role' => 'member'
        ];

        $response = $this->postJson("/api/workspaces/{$this->workspace->id}/invite", $data);

        $response->assertStatus(409);
        $response->assertJson([
            'error' => 'User is already a member of this workspace'
        ]);
    }

    
    public function test_owner_can_remove_member()
    {
        $this->actingAs($this->user, 'api');

        $response = $this->deleteJson("/api/workspaces/{$this->workspace->id}/members/{$this->memberUser->id}");

        $response->assertStatus(200);
        $response->assertJson([
            'message' => 'Member removed successfully'
        ]);

        // Verify member was removed
        $this->assertDatabaseMissing('user_workspace', [
            'user_id' => $this->memberUser->id,
            'workspace_id' => $this->workspace->id
        ]);
    }

    
    public function test_owner_cannot_remove_self()
    {
        $this->actingAs($this->user, 'api');

        $response = $this->deleteJson("/api/workspaces/{$this->workspace->id}/members/{$this->user->id}");

        $response->assertStatus(403);
        $response->assertJson([
            'error' => 'Cannot remove yourself from workspace'
        ]);

        // Verify owner is still a member
        $this->assertDatabaseHas('user_workspace', [
            'user_id' => $this->user->id,
            'workspace_id' => $this->workspace->id
        ]);
    }

    
    public function test_member_can_leave_workspace()
    {
        $this->actingAs($this->memberUser, 'api');

        $response = $this->postJson("/api/workspaces/{$this->workspace->id}/leave");

        $response->assertStatus(200);
        $response->assertJson([
            'message' => 'You have left the workspace'
        ]);

        // Verify member was removed
        $this->assertDatabaseMissing('user_workspace', [
            'user_id' => $this->memberUser->id,
            'workspace_id' => $this->workspace->id
        ]);
    }

    
    public function test_owner_cannot_leave_workspace()
    {
        $this->actingAs($this->user, 'api');

        $response = $this->postJson("/api/workspaces/{$this->workspace->id}/leave");

        $response->assertStatus(403);
        $response->assertJson([
            'error' => 'Workspace owner cannot leave. Transfer ownership or delete workspace.'
        ]);

        // Verify owner is still a member
        $this->assertDatabaseHas('user_workspace', [
            'user_id' => $this->user->id,
            'workspace_id' => $this->workspace->id
        ]);
    }

    
    public function test_owner_can_delete_workspace()
    {
        $this->actingAs($this->user, 'api');

        $response = $this->deleteJson("/api/workspaces/{$this->workspace->id}");

        $response->assertStatus(200);
        $response->assertJson([
            'message' => 'Deleted successfully'
        ]);

        // Verify workspace was soft deleted (if using soft deletes)
        $this->assertSoftDeleted('workspaces', [
            'id' => $this->workspace->id
        ]);
    }

    
    public function test_member_cannot_delete_workspace()
    {
        $this->actingAs($this->memberUser, 'api');

        $response = $this->deleteJson("/api/workspaces/{$this->workspace->id}");

        $response->assertStatus(403);
        $response->assertJson([
            'error' => 'Only workspace owners can delete the workspace'
        ]);

        // Verify workspace still exists
        $this->assertDatabaseHas('workspaces', [
            'id' => $this->workspace->id
        ]);
    }

    
    public function test_unauthenticated_user_cannot_access_workspace_endpoints()
    {
        // Test create
        $response = $this->postJson('/api/workspaces', ['name' => 'Test']);
        $response->assertStatus(401);

        // Test show
        $response = $this->getJson("/api/workspaces/{$this->workspace->id}");
        $response->assertStatus(401);

        // Test update
        $response = $this->putJson("/api/workspaces/{$this->workspace->id}", ['name' => 'Test']);
        $response->assertStatus(401);

        // Test delete
        $response = $this->deleteJson("/api/workspaces/{$this->workspace->id}");
        $response->assertStatus(401);
    }

    
    public function test_workspace_details_includes_correct_member_roles()
    {
        // Add a guest user
        $guestUser = User::factory()->create(['email' => 'guest@example.com']);
        $guestUser->workspaces()->attach($this->workspace->id, [
            'role' => 'guest'
        ]);

        $this->actingAs($this->user, 'api');

        $response = $this->getJson("/api/workspaces/{$this->workspace->id}");

        $response->assertStatus(200);

        // Get all roles from response
        $members = $response->json('members');
        $roles = array_column($members, column_key: 'role');

        // Should have all three roles
        $this->assertContains('owner', $roles);
        $this->assertContains('member', $roles);
        $this->assertContains('guest', $roles);

        // Check specific user roles
        foreach ($members as $member) {
            if ($member['email'] === 'owner@example.com') {
                $this->assertEquals('owner', $member['role']);
            } elseif ($member['email'] === 'member@example.com') {
                $this->assertEquals('member', $member['role']);
            } elseif ($member['email'] === 'guest@example.com') {
                $this->assertEquals('guest', $member['role']);
            }
        }
    }
}
