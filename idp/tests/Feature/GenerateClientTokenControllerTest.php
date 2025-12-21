<?php

namespace Tests\Feature;

use Tests\TestCase;
use Illuminate\Support\Facades\Http;
use Laravel\Passport\Client;
use Illuminate\Support\Facades\Hash;
use Illuminate\Foundation\Testing\RefreshDatabase;

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
        // Mock the external HTTP request
        Http::fake([
            'http://sina-idp-service/oauth/token' => Http::response([
                'access_token' => 'mocked_token'
            ], 200)
        ]);

        $response = $this->postJson(route('internal.client-token'), [
            'client_id' => $this->client->id,
            'client_secret' => 'supersecret'
        ]);

        $response->assertStatus(200)
                 ->assertJson(['token' => 'mocked_token']);

        // Ensure the HTTP request was sent
        Http::assertSent(function ($request) {
            return $request->url() === 'http://sina-idp-service/oauth/token' &&
                   $request['grant_type'] === 'client_credentials';
        });
    }

    public function test_it_returns_error_when_token_request_fails()
    {
        // Simulate failed response from OAuth server
        Http::fake([
            'http://sina-idp-service/oauth/token' => Http::response([], 500)
        ]);

        $response = $this->postJson(route('internal.client-token'), [
            'client_id' => $this->client->id,
            'client_secret' => 'supersecret'
        ]);

        $response->assertStatus(500)
                 ->assertJson(['msg' => 'operation failed !']);
    }
}
