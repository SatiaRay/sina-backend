<?php

namespace Tests\Feature;

use Tests\TestCase;
use Illuminate\Support\Facades\Http;
use Laravel\Passport\Client;
use Illuminate\Support\Facades\Hash;
use Illuminate\Foundation\Testing\RefreshDatabase;
use League\OAuth2\Server\AuthorizationServer;

class GenerateClientTokenControllerTest extends TestCase
{
    use RefreshDatabase;

    protected $client;

    protected function setUp(): void
    {
        parent::setUp();

        // Create a valid client
        $this->client = Client::factory()->create([
            'secret' => Hash::make('supersecret'),
            'revoked' => false,
        ]);
    }

    public function test_it_rejects_requests_without_credentials()
    {
        $response = $this->postJson(route('internal.client-token'));

        $response->assertStatus(403)
            ->assertJson(['msg' => 'Credentials are required!']);
    }

    public function test_it_rejects_invalid_client_id()
    {
        $response = $this->postJson(route('internal.client-token'), [
            'client_id' => 999,
            'client_secret' => 'supersecret'
        ]);

        $response->assertStatus(403)
            ->assertJson(['msg' => 'Invalid client ID.']);
    }

    public function test_it_rejects_invalid_client_secret()
    {
        $response = $this->postJson(route('internal.client-token'), [
            'client_id' => $this->client->id,
            'client_secret' => 'wrongsecret'
        ]);

        $response->assertStatus(403)
            ->assertJson(['msg' => 'Invalid client secret.']);
    }

    public function test_it_returns_token_when_credentials_are_valid()
    {
        // Mock the AuthorizationServer
        $mockServer = $this->mock(AuthorizationServer::class);

        $mockResponse = new \GuzzleHttp\Psr7\Response(200, [], json_encode([
            'access_token' => 'mocked_token',
            'token_type' => 'Bearer',
            'expires_in' => 86400
        ]));

        $mockServer->shouldReceive('respondToAccessTokenRequest')
            ->once()
            ->andReturn($mockResponse);

        $response = $this->postJson(route('internal.client-token'), [
            'client_id' => $this->client->id,
            'client_secret' => 'supersecret'
        ]);

        $response->assertStatus(200)
            ->assertJson(['token' => 'mocked_token']);
    }

    public function test_it_returns_error_when_token_request_fails()
    {
        // Mock the AuthorizationServer to throw an exception
        $mockServer = $this->mock(AuthorizationServer::class);

        $mockServer->shouldReceive('respondToAccessTokenRequest')
            ->once()
            ->andThrow(new \Exception('Server error'));

        $response = $this->postJson(route('internal.client-token'), [
            'client_id' => $this->client->id,
            'client_secret' => 'supersecret'
        ]);

        $response->assertStatus(500)
            ->assertJson(['msg' => 'operation failed !']);
    }
}
