<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Hash;
use Tests\TestCase;

class AuthControllerTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        // Ensure Passport personal access client exists for tests
        \Laravel\Passport\Client::factory()->create([
            'id' => 1,
            'name' => 'Test Personal Access Client',
            'secret' => 'test-secret',
            'redirect_uris' => ['http://localhost'],
            'grant_types' => ['personal_access'],
            'revoked' => false,
        ]);
    }

    public function test_user_can_register()
    {
        $response = $this->postJson('api/register', [
            'name' => 'Test User',
            'email' => 'test@example.com',
            'password' => 'password123',
            'password_confirmation' => 'password123',
        ]);

        $response
            ->assertStatus(201)
            ->assertJsonStructure([
                'user' => ['id', 'name', 'email', 'primary_workspace_id', 'created_at', 'updated_at'],
                'token',
            ]);

        $this->assertDatabaseHas('users', [
            'email' => 'test@example.com',
        ]);

        // Check that a workspace was created for the user
        $user = User::where('email', 'test@example.com')->first();
        $this->assertNotNull($user->primary_workspace_id);
        
        // Check workspace exists
        $this->assertDatabaseHas('workspaces', [
            'id' => $user->primary_workspace_id,
        ]);
        
        // Check user is attached to the workspace as owner
        $this->assertDatabaseHas('user_workspace', [
            'user_id' => $user->id,
            'workspace_id' => $user->primary_workspace_id,
            'role' => 'owner',
        ]);
    }

    public function test_user_can_login()
    {
        $user = User::factory()->create([
            'email' => 'login@example.com',
            'password' => Hash::make('password123'),
        ]);

        // Since register now creates a workspace, we need to simulate that
        $workspace = \App\Models\Workspace::factory()->create([
            'name' => "{$user->name}'s Workspace",
        ]);
        $user->workspaces()->attach($workspace->id, ['role' => 'owner']);
        $user->update(['primary_workspace_id' => $workspace->id]);

        $response = $this->postJson('api/login', [
            'email' => 'login@example.com',
            'password' => 'password123',
        ]);

        $response
            ->assertStatus(200)
            ->assertJsonStructure([
                'user' => ['id', 'name', 'email', 'primary_workspace_id', 'created_at', 'updated_at'],
                'token',
            ]);
    }

    public function test_user_can_logout()
    {
        // Create a user
        $user = User::factory()->create();

        // Create a workspace for the user (simulating registration)
        $workspace = \App\Models\Workspace::factory()->create([
            'name' => "{$user->name}'s Workspace",
        ]);
        $user->workspaces()->attach($workspace->id, ['role' => 'owner']);
        $user->update(['primary_workspace_id' => $workspace->id]);

        $token = $user->createToken('SSO')->accessToken;

        $response = $this->withHeaders([
            'Authorization' => 'Bearer ' . $token,
        ])->postJson('api/logout');

        $response
            ->assertStatus(200)
            ->assertJson([
                'message' => 'Successfully logged out',
            ]);
    }

    public function test_user_can_switch_workspace()
    {
        // Create a user with their default workspace
        $user = User::factory()->create([
            'password' => Hash::make('password123'),
        ]);

        // Create default workspace (simulating registration)
        $defaultWorkspace = \App\Models\Workspace::factory()->create([
            'name' => "{$user->name}'s Workspace",
        ]);
        $user->workspaces()->attach($defaultWorkspace->id, ['role' => 'owner']);
        $user->update(['primary_workspace_id' => $defaultWorkspace->id]);

        // Create additional workspace for switching
        $additionalWorkspace = \App\Models\Workspace::factory()->create();
        $user->workspaces()->attach($additionalWorkspace->id, ['role' => 'member']);

        // First, login to get initial token
        $loginResponse = $this->postJson('api/login', [
            'email' => $user->email,
            'password' => 'password123',
            'workspace_id' => $defaultWorkspace->id,
        ]);

        $initialToken = $loginResponse->json('token');

        // Now test switching to additional workspace
        $switchResponse = $this->withHeaders([
            'Authorization' => 'Bearer ' . $initialToken,
        ])->postJson('api/switch-workspace', [
            'workspace_id' => $additionalWorkspace->id,
        ]);

        $switchResponse
            ->assertStatus(200)
            ->assertJsonStructure([
                'user' => ['id', 'name', 'email', 'primary_workspace_id'],
                'token',
                'workspace_id',
            ])
            ->assertJson([
                'workspace_id' => $additionalWorkspace->id,
            ]);

        $newToken = $switchResponse->json('token');
        $this->assertNotEquals($initialToken, $newToken, 'Token should be regenerated');
    }

    public function test_user_cannot_switch_to_unauthorized_workspace()
    {
        $user = User::factory()->create([
            'password' => Hash::make('password123'),
        ]);

        // Create default workspace (simulating registration)
        $defaultWorkspace = \App\Models\Workspace::factory()->create([
            'name' => "{$user->name}'s Workspace",
        ]);
        $user->workspaces()->attach($defaultWorkspace->id, ['role' => 'owner']);
        $user->update(['primary_workspace_id' => $defaultWorkspace->id]);

        // Create unauthorized workspace (user not attached)
        $unauthorizedWorkspace = \App\Models\Workspace::factory()->create();

        // Login
        $loginResponse = $this->postJson('api/login', [
            'email' => $user->email,
            'password' => 'password123',
        ]);

        $token = $loginResponse->json('token');

        // Try to switch to unauthorized workspace
        $response = $this->withHeaders([
            'Authorization' => 'Bearer ' . $token,
        ])->postJson('api/switch-workspace', [
            'workspace_id' => $unauthorizedWorkspace->id,
        ]);

        $response
            ->assertStatus(403)
            ->assertJson([
                'message' => 'You do not have access to this workspace.',
            ]);
    }

    public function test_switch_workspace_requires_authentication()
    {
        // Try to switch workspace without authentication
        $response = $this->postJson('api/switch-workspace', [
            'workspace_id' => 'some-workspace-id',
        ]);

        $response->assertStatus(401);
    }

    public function test_switch_workspace_requires_valid_workspace_id()
    {
        $user = User::factory()->create([
            'password' => Hash::make('password123'),
        ]);

        // Create default workspace (simulating registration)
        $defaultWorkspace = \App\Models\Workspace::factory()->create([
            'name' => "{$user->name}'s Workspace",
        ]);
        $user->workspaces()->attach($defaultWorkspace->id, ['role' => 'owner']);
        $user->update(['primary_workspace_id' => $defaultWorkspace->id]);

        // Login
        $loginResponse = $this->postJson('api/login', [
            'email' => $user->email,
            'password' => 'password123',
        ]);

        $token = $loginResponse->json('token');

        // Test with non-existent workspace
        $response = $this->withHeaders([
            'Authorization' => 'Bearer ' . $token,
        ])->postJson('api/switch-workspace', [
            'workspace_id' => 'non-existent-workspace-id',
        ]);

        $response->assertStatus(422);

        // Test without workspace_id
        $response = $this->withHeaders([
            'Authorization' => 'Bearer ' . $token,
        ])->postJson('api/switch-workspace', []);

        $response->assertStatus(422);
    }

    public function test_login_falls_back_to_primary_workspace_when_no_access_to_requested()
    {
        $user = User::factory()->create([
            'password' => Hash::make('password123'),
        ]);

        // Create default workspace (simulating registration)
        $defaultWorkspace = \App\Models\Workspace::factory()->create([
            'name' => "{$user->name}'s Workspace",
        ]);
        $user->workspaces()->attach($defaultWorkspace->id, ['role' => 'owner']);
        $user->update(['primary_workspace_id' => $defaultWorkspace->id]);

        // Create other workspace (user not attached)
        $otherWorkspace = \App\Models\Workspace::factory()->create();

        // Try to login with workspace user doesn't have access to
        $response = $this->postJson('api/login', [
            'email' => $user->email,
            'password' => 'password123',
            'workspace_id' => $otherWorkspace->id, // User doesn't have access to this
        ]);

        $response
            ->assertStatus(200)
            ->assertJson([
                'workspace_id' => $defaultWorkspace->id, // Should fall back to primary
            ]);
    }

    public function test_user_can_switch_back_and_forth_between_workspaces()
    {
        $user = User::factory()->create([
            'password' => Hash::make('password123'),
        ]);

        // Create default workspace (simulating registration)
        $defaultWorkspace = \App\Models\Workspace::factory()->create([
            'name' => "{$user->name}'s Workspace",
        ]);
        $user->workspaces()->attach($defaultWorkspace->id, ['role' => 'owner']);
        $user->update(['primary_workspace_id' => $defaultWorkspace->id]);

        // Create additional workspace
        $additionalWorkspace = \App\Models\Workspace::factory()->create();
        $user->workspaces()->attach($additionalWorkspace->id, ['role' => 'member']);

        // Login with default workspace
        $loginResponse = $this->postJson('api/login', [
            'email' => $user->email,
            'password' => 'password123',
            'workspace_id' => $defaultWorkspace->id,
        ]);

        $token = $loginResponse->json('token');

        // Switch to additional workspace
        $response1 = $this->withHeaders([
            'Authorization' => 'Bearer ' . $token,
        ])->postJson('api/switch-workspace', [
            'workspace_id' => $additionalWorkspace->id,
        ]);

        $token2 = $response1->json('token');
        $response1->assertJson(['workspace_id' => $additionalWorkspace->id]);

        // Switch back to default workspace
        $response2 = $this->withHeaders([
            'Authorization' => 'Bearer ' . $token2,
        ])->postJson('api/switch-workspace', [
            'workspace_id' => $defaultWorkspace->id,
        ]);

        $response2
            ->assertStatus(200)
            ->assertJson(['workspace_id' => $defaultWorkspace->id]);
    }

    public function test_new_user_has_default_workspace_created()
    {
        $response = $this->postJson('api/register', [
            'name' => 'John Doe',
            'email' => 'john@example.com',
            'password' => 'password123',
            'password_confirmation' => 'password123',
        ]);

        $response->assertStatus(201);

        $user = User::where('email', 'john@example.com')->first();
        
        // Verify user has primary workspace set
        $this->assertNotNull($user->primary_workspace_id);
        
        // Verify workspace was created with correct name
        $workspace = \App\Models\Workspace::find($user->primary_workspace_id);
        $this->assertNotNull($workspace);
        $this->assertEquals("John Doe's Workspace", $workspace->name);
        
        // Verify user is attached as owner
        $this->assertDatabaseHas('user_workspace', [
            'user_id' => $user->id,
            'workspace_id' => $workspace->id,
            'role' => 'owner',
        ]);
    }
}