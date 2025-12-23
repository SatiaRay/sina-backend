<?php

namespace Tests\Feature\Api;

use Tests\TestCase;
use Laravel\Passport\Client;
use Laravel\Passport\Token;
use Laravel\Passport\RefreshToken;
use App\Models\User;
use Carbon\Carbon;
use Illuminate\Support\Facades\Hash;
use Illuminate\Foundation\Testing\RefreshDatabase;

class OAuthIntrospectionTest extends TestCase
{
    use RefreshDatabase;
    
    protected $user;
    protected $introspectionClient;
    protected $personalAccessClient;
    
    protected function setUp(): void
    {
        parent::setUp();
        
        // Create a user for testing
        $this->user = User::factory()->create([
            'email' => 'test@example.com',
            'password' => Hash::make('password123')
        ]);
        
        // Create a personal access client (required for createToken())
        $this->personalAccessClient = new Client();
        $this->personalAccessClient->id = \Illuminate\Support\Str::orderedUuid();
        $this->personalAccessClient->owner_id = null;
        $this->personalAccessClient->owner_type = null;
        $this->personalAccessClient->name = 'Laravel Personal Access Client';
        $this->personalAccessClient->secret = null;
        $this->personalAccessClient->redirect_uris = [];
        $this->personalAccessClient->grant_types = ['personal_access'];
        $this->personalAccessClient->revoked = false;
        $this->personalAccessClient->save();
        
        // Create a client for introspection
        $this->introspectionClient = new Client();
        $this->introspectionClient->id = \Illuminate\Support\Str::orderedUuid();
        $this->introspectionClient->owner_id = $this->user->id;
        $this->introspectionClient->owner_type = User::class;
        $this->introspectionClient->name = 'Introspection Client';
        $this->introspectionClient->secret = Hash::make('introspection-secret');
        $this->introspectionClient->redirect_uris = [];
        $this->introspectionClient->grant_types = ['client_credentials'];
        $this->introspectionClient->revoked = false;
        $this->introspectionClient->save();
    }
    
    protected function getBasicAuthHeader($clientId, $clientSecret)
    {
        $credentials = base64_encode($clientId . ':' . $clientSecret);
        return ['Authorization' => 'Basic ' . $credentials];
    }
    
    /**
     * Make a POST request with form-urlencoded data
     */
    protected function postIntrospect($data = [], $headers = [])
    {
        $headers = array_merge([
            'Accept' => 'application/json',
            'Content-Type' => 'application/x-www-form-urlencoded',
        ], $headers);
        
        return $this->call('POST', '/api/oauth/introspect', $data, [], [], 
            $this->transformHeadersToServerVars($headers));
    }
    
    /**
     * Create a real access token for testing
     */
    protected function createAccessToken($scopes = ['*'])
    {
        // For personal access tokens, use '*' or empty array
        $tokenResult = $this->user->createToken('Test Token', $scopes);
        return $tokenResult->accessToken;
    }
    
    /**
     * Create a refresh token for testing
     */
    protected function createRefreshToken()
    {
        // Create an access token first
        $tokenResult = $this->user->createToken('Test Token');
        $accessToken = $tokenResult->token;
        
        // Create a refresh token
        $refreshToken = new RefreshToken();
        $refreshToken->id = 'test-refresh-' . uniqid();
        $refreshToken->access_token_id = $accessToken->id;
        $refreshToken->revoked = false;
        $refreshToken->expires_at = Carbon::now()->addDays(7);
        $refreshToken->save();
        
        return $refreshToken;
    }
    
    /**
     * Test successful introspection with valid access token
     */
    public function test_successful_access_token_introspection_with_basic_auth()
    {
        $accessToken = $this->createAccessToken();

        $response = $this->postIntrospect([
            'token' => $accessToken,
        ], $this->getBasicAuthHeader(
            $this->introspectionClient->id,
            'introspection-secret'
        ));
        
        $response->assertStatus(200);
        $response->assertJson([
            'active' => true,
            'token_type' => 'access_token',
            'username' => $this->user->email,
        ]);
    }
    
    /**
     * Test successful introspection with client credentials in body
     */
    public function test_successful_introspection_with_credentials_in_body()
    {
        $accessToken = $this->createAccessToken();
        
        $response = $this->postIntrospect([
            'token' => $accessToken,
            'client_id' => $this->introspectionClient->id,
            'client_secret' => 'introspection-secret',
        ]);
        
        $response->assertStatus(200);
        $response->assertJson(['active' => true]);
    }
    
    /**
     * Test introspection with revoked access token
     */
    public function test_introspection_with_revoked_access_token()
    {
        $accessToken = $this->createAccessToken();
        
        // Revoke all user tokens
        $this->user->tokens()->delete();
        
        $response = $this->postIntrospect([
            'token' => $accessToken,
        ], $this->getBasicAuthHeader(
            $this->introspectionClient->id,
            'introspection-secret'
        ));
        
        $response->assertStatus(200);
        $response->assertExactJson(['active' => false]);
    }
    
    /**
     * Test introspection with expired access token
     */
    public function test_introspection_with_expired_access_token()
    {
        // Create token
        $tokenResult = $this->user->createToken('Expired Token');
        $accessTokenString = $tokenResult->accessToken;
        $token = $tokenResult->token;
        
        // Manually expire it
        $token->expires_at = Carbon::now()->subHour();
        $token->save();
        
        $response = $this->postIntrospect([
            'token' => $accessTokenString,
        ], $this->getBasicAuthHeader(
            $this->introspectionClient->id,
            'introspection-secret'
        ));
        
        $response->assertStatus(200);
        $response->assertExactJson(['active' => false]);
    }
    
    /**
     * Test introspection with non-existent token
     */
    public function test_introspection_with_non_existent_token()
    {
        $response = $this->postIntrospect([
            'token' => 'non-existent-token-' . uniqid(),
        ], $this->getBasicAuthHeader(
            $this->introspectionClient->id,
            'introspection-secret'
        ));
        
        $response->assertStatus(200);
        $response->assertExactJson(['active' => false]);
    }
    
    /**
     * Test introspection with invalid JWT token
     */
    public function test_introspection_with_invalid_jwt_token()
    {
        $response = $this->postIntrospect([
            'token' => 'invalid.jwt.token',
        ], $this->getBasicAuthHeader(
            $this->introspectionClient->id,
            'introspection-secret'
        ));
        
        $response->assertStatus(200);
        $response->assertExactJson(['active' => false]);
    }
    
    /**
     * Test refresh token introspection with hint
     */
    public function test_successful_refresh_token_introspection_with_hint()
    {
        $refreshToken = $this->createRefreshToken();
        
        $response = $this->postIntrospect([
            'token' => $refreshToken->id,
            'token_type_hint' => 'refresh_token',
        ], $this->getBasicAuthHeader(
            $this->introspectionClient->id,
            'introspection-secret'
        ));
        
        $response->assertStatus(200);
        $response->assertJson([
            'active' => true,
            'token_type' => 'refresh_token',
            'username' => $this->user->email,
        ]);
    }
    
    /**
     * Test introspection with revoked refresh token
     */
    public function test_introspection_with_revoked_refresh_token()
    {
        $refreshToken = $this->createRefreshToken();
        $refreshToken->revoked = true;
        $refreshToken->save();
        
        $response = $this->postIntrospect([
            'token' => $refreshToken->id,
            'token_type_hint' => 'refresh_token',
        ], $this->getBasicAuthHeader(
            $this->introspectionClient->id,
            'introspection-secret'
        ));
        
        $response->assertStatus(200);
        $response->assertExactJson(['active' => false]);
    }
    
    /**
     * Test introspection without client authentication
     */
    public function test_introspection_without_client_authentication()
    {
        $accessToken = $this->createAccessToken();
        
        $response = $this->postIntrospect([
            'token' => $accessToken,
        ]);
        
        $response->assertStatus(401);
        $response->assertJson([
            'error' => 'invalid_client',
        ]);
    }
    
    /**
     * Test introspection with invalid client credentials
     */
    public function test_introspection_with_invalid_client_credentials()
    {
        $accessToken = $this->createAccessToken();
        
        $response = $this->postIntrospect([
            'token' => $accessToken,
        ], $this->getBasicAuthHeader(
            $this->introspectionClient->id,
            'wrong-secret'
        ));
        
        $response->assertStatus(401);
        $response->assertJson([
            'error' => 'invalid_client',
        ]);
    }
    
    /**
     * Test introspection with revoked client
     */
    public function test_introspection_with_revoked_client()
    {
        $accessToken = $this->createAccessToken();
        
        $this->introspectionClient->revoked = true;
        $this->introspectionClient->save();
        
        $response = $this->postIntrospect([
            'token' => $accessToken,
        ], $this->getBasicAuthHeader(
            $this->introspectionClient->id,
            'introspection-secret'
        ));
        
        $response->assertStatus(401);
        $response->assertJson([
            'error' => 'invalid_client',
        ]);
    }
    
    /**
     * Test introspection with missing token parameter
     */
    public function test_introspection_with_missing_token()
    {
        $response = $this->postIntrospect([
            // No token provided
        ], $this->getBasicAuthHeader(
            $this->introspectionClient->id,
            'introspection-secret'
        ));
        
        $response->assertStatus(422);
        $response->assertJsonValidationErrors(['token']);
    }
    
    /**
     * Test introspection with invalid token type hint
     */
    public function test_introspection_with_invalid_token_type_hint()
    {
        $accessToken = $this->createAccessToken();
        
        $response = $this->postIntrospect([
            'token' => $accessToken,
            'token_type_hint' => 'invalid_hint',
        ], $this->getBasicAuthHeader(
            $this->introspectionClient->id,
            'introspection-secret'
        ));
        
        $response->assertStatus(422);
        $response->assertJsonValidationErrors(['token_type_hint']);
    }
    
    /**
     * Test introspection returns correct scope formatting
     */
    public function test_scope_formatting()
    {
        // For scope testing, we need to manually set scopes on the token
        // since Passport doesn't validate scopes for personal access tokens
        
        // First create a token
        $tokenResult = $this->user->createToken('Test Token');
        $accessTokenString = $tokenResult->accessToken;
        $token = $tokenResult->token;
        
        // Manually set scopes on the token
        $token->scopes = json_encode(['read', 'write', 'delete']);
        $token->save();
        
        $response = $this->postIntrospect([
            'token' => $accessTokenString,
        ], $this->getBasicAuthHeader(
            $this->introspectionClient->id,
            'introspection-secret'
        ));
        
        $response->assertStatus(200);
        $this->assertTrue($response->json('active'));
        
        $scope = $response->json('scope');
        // Scope should contain all three scopes
        $this->assertStringContainsString('read', $scope);
        $this->assertStringContainsString('write', $scope);
        $this->assertStringContainsString('delete', $scope);
    }
    
    /**
     * Test introspection with plain text client secret (fallback)
     */
    public function test_introspection_with_plain_text_client_secret()
    {
        $accessToken = $this->createAccessToken();
        
        $plainTextClient = new Client();
        $plainTextClient->id = \Illuminate\Support\Str::orderedUuid();
        $plainTextClient->owner_id = $this->user->id;
        $plainTextClient->owner_type = User::class;
        $plainTextClient->name = 'Plain Text Client';
        $plainTextClient->secret = 'plain-text-secret'; // Not hashed
        $plainTextClient->redirect_uris = [];
        $plainTextClient->grant_types = ['client_credentials'];
        $plainTextClient->revoked = false;
        $plainTextClient->save();
        
        $response = $this->postIntrospect([
            'token' => $accessToken,
        ], $this->getBasicAuthHeader(
            $plainTextClient->id,
            'plain-text-secret'
        ));
        
        $response->assertStatus(200);
        $response->assertJson(['active' => true]);
    }
    
    /**
     * Test introspection with expired refresh token
     */
    public function test_introspection_with_expired_refresh_token()
    {
        $refreshToken = $this->createRefreshToken();
        $refreshToken->expires_at = Carbon::now()->subHour();
        $refreshToken->save();
        
        $response = $this->postIntrospect([
            'token' => $refreshToken->id,
            'token_type_hint' => 'refresh_token',
        ], $this->getBasicAuthHeader(
            $this->introspectionClient->id,
            'introspection-secret'
        ));
        
        $response->assertStatus(200);
        $response->assertExactJson(['active' => false]);
    }
}