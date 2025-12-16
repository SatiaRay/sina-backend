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
        // Ensure Passport personal access client exists for tests (arrays, not JSON)
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
                'user' => ['id', 'name', 'email', 'created_at', 'updated_at'],
                'token',
            ]);

        $this->assertDatabaseHas('users', [
            'email' => 'test@example.com',
        ]);
    }

    public function test_user_can_login()
    {
        $user = User::factory()->create([
            'email' => 'login@example.com',
            'password' => Hash::make('password123'),
        ]);

        $response = $this->postJson('api/login', [
            'email' => 'login@example.com',
            'password' => 'password123',
        ]);

        $response
            ->assertStatus(200)
            ->assertJsonStructure([
                'user' => ['id', 'name', 'email', 'created_at', 'updated_at'],
                'token',
            ]);
    }

    public function test_user_can_logout()
    {
        // Create a user with a workspace
        $user = User::factory()->create();

        // Create a workspace for the user
        $workspace = \App\Models\Workspace::factory()->create();

        // Attach user to workspace (adjust based on your relationship setup)
        $user->workspaces()->attach($workspace->id, ['role' => 'member']);

        // Set primary workspace if needed by your logic
        $user->update(['primary_workspace_id' => $workspace->id]);

        $token = $user->createToken('SSO')->accessToken;

        $response = $this->withHeaders([
            'Authorization' => 'Bearer ' . $token,
            'X-Workspace-Id' => $workspace->id, // Add workspace header
        ])->postJson('api/logout');

        $response
            ->assertStatus(200)
            ->assertJson([
                'message' => 'Successfully logged out',
            ]);
    }
}
