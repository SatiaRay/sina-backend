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
use Mockery;

class OAuthIntrospectionTest extends TestCase
{
    use RefreshDatabase;
    
    protected $client;
    protected $user;
    protected $accessToken;
    protected $refreshToken;
    protected $introspectionClient;
    protected $mockParser;
    
    protected function setUp(): void
    {
        parent::setUp();
        
        // Create a user for testing
        $this->user = User::factory()->create([
            'email' => 'test@example.com',
            'password' => Hash::make('password123')
        ]);
        
        // Create a client for issuing tokens - using owner relationship
        $this->client = Client::create([
            'owner_id' => $this->user->id,
            'owner_type' => User::class,
            'name' => 'Test Client',
            'secret' => Hash::make('client-secret'),
            'redirect_uris' => json_encode(['http://localhost/callback']),
            'grant_types' => json_encode(['password', 'refresh_token']),
            'revoked' => false,
        ]);
        
        // Create a separate client for introspection
        $this->introspectionClient = Client::create([
            'owner_id' => $this->user->id,
            'owner_type' => User::class,
            'name' => 'Introspection Client',
            'secret' => Hash::make('introspection-secret'),
            'redirect_uris' => json_encode(['http://localhost/callback']),
            'grant_types' => json_encode(['client_credentials']),
            'revoked' => false,
        ]);
        
        // Create test access token
        $this->accessToken = $this->createTestAccessToken();
        
        // Create test refresh token
        $this->refreshToken = $this->createTestRefreshToken();
    }
    
    protected function tearDown(): void
    {
        Mockery::close();
        parent::tearDown();
    }
    
    protected function createTestAccessToken()
    {
        $token = new Token([
            'id' => 'test-token-id-' . uniqid(),
            'user_id' => $this->user->id,
            'client_id' => $this->client->id,
            'name' => 'Test Token',
            'scopes' => json_encode(['read', 'write']),
            'revoked' => false,
            'created_at' => Carbon::now()->subHour(),
            'updated_at' => Carbon::now(),
            'expires_at' => Carbon::now()->addHour(),
        ]);
        $token->save();
        
        return $token;
    }
    
    protected function createTestRefreshToken()
    {
        $refreshToken = new RefreshToken([
            'id' => 'test-refresh-token-' . uniqid(),
            'access_token_id' => $this->accessToken->id,
            'revoked' => false,
            'expires_at' => Carbon::now()->addDays(7),
        ]);
        $refreshToken->save();
        
        return $refreshToken;
    }
    
    protected function getBasicAuthHeader($clientId, $clientSecret)
    {
        $credentials = base64_encode($clientId . ':' . $clientSecret);
        return ['Authorization' => 'Basic ' . $credentials];
    }
    
    /**
     * Helper method to mock JWT parser for access token tests
     */
    protected function mockJwtParserForAccessToken($tokenId = null)
    {
        $mockToken = Mockery::mock('overload:Lcobucci\JWT\Token');
        $mockClaims = Mockery::mock();
        
        $mockClaims->shouldReceive('get')
            ->with('jti')
            ->andReturn($tokenId ?? $this->accessToken->id);
        
        $mockToken->shouldReceive('claims')
            ->andReturn($mockClaims);
        
        $mockParser = Mockery::mock('overload:Lcobucci\JWT\Token\Parser');
        $mockParser->shouldReceive('parse')
            ->andReturn($mockToken);
    }
    
    /**
     * Helper method to mock JWT parser to throw exception
     */
    protected function mockJwtParserToThrowException()
    {
        $mockParser = Mockery::mock('overload:Lcobucci\JWT\Token\Parser');
        $mockParser->shouldReceive('parse')
            ->andThrow(new \Exception('Invalid JWT'));
    }
    
    /**
     * Test successful introspection with valid access token
     */
    public function test_successful_access_token_introspection_with_basic_auth()
    {
        $this->mockJwtParserForAccessToken();
        
        $response = $this->post('/api/oauth/introspect', [
            'token' => 'any-jwt-token',
        ], $this->getBasicAuthHeader(
            $this->introspectionClient->id,
            'introspection-secret'
        ));
        
        $response->assertStatus(200);
        $response->assertJson([
            'active' => true,
            'token_type' => 'access_token',
            'client_id' => (string) $this->client->id,
            'username' => $this->user->email,
            'sub' => (string) $this->user->id,
        ]);
    }
    
    /**
     * Test successful introspection with client credentials in body
     */
    public function test_successful_introspection_with_credentials_in_body()
    {
        $this->mockJwtParserForAccessToken();
        
        $response = $this->post('/api/oauth/introspect', [
            'token' => 'any-jwt-token',
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
        $this->mockJwtParserForAccessToken();
        
        $this->accessToken->revoked = true;
        $this->accessToken->save();
        
        $response = $this->post('/api/oauth/introspect', [
            'token' => 'any-jwt-token',
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
        $this->mockJwtParserForAccessToken();
        
        $this->accessToken->expires_at = Carbon::now()->subHour();
        $this->accessToken->save();
        
        $response = $this->post('/api/oauth/introspect', [
            'token' => 'any-jwt-token',
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
        $this->mockJwtParserToThrowException();
        
        $response = $this->post('/api/oauth/introspect', [
            'token' => 'non-existent-token',
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
        $this->mockJwtParserToThrowException();
        
        $response = $this->post('/api/oauth/introspect', [
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
        // Mock JWT parser to throw exception so it falls back to refresh token check
        $this->mockJwtParserToThrowException();
        
        $response = $this->post('/api/oauth/introspect', [
            'token' => $this->refreshToken->id,
            'token_type_hint' => 'refresh_token',
        ], $this->getBasicAuthHeader(
            $this->introspectionClient->id,
            'introspection-secret'
        ));
        
        $response->assertStatus(200);
        $response->assertJson([
            'active' => true,
            'token_type' => 'refresh_token',
            'client_id' => (string) $this->client->id,
            'username' => $this->user->email,
        ]);
    }
    
    /**
     * Test introspection with revoked refresh token
     */
    public function test_introspection_with_revoked_refresh_token()
    {
        $this->refreshToken->revoked = true;
        $this->refreshToken->save();
        
        // Mock JWT parser to throw exception so it falls back to refresh token check
        $this->mockJwtParserToThrowException();
        
        $response = $this->post('/api/oauth/introspect', [
            'token' => $this->refreshToken->id,
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
        $this->mockJwtParserForAccessToken();
        
        $response = $this->post('/api/oauth/introspect', [
            'token' => 'any-jwt-token',
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
        $this->mockJwtParserForAccessToken();
        
        $response = $this->post('/api/oauth/introspect', [
            'token' => 'any-jwt-token',
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
        $this->mockJwtParserForAccessToken();
        
        $this->introspectionClient->revoked = true;
        $this->introspectionClient->save();
        
        $response = $this->post('/api/oauth/introspect', [
            'token' => 'any-jwt-token',
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
    $this->mockJwtParserForAccessToken();
    
    $response = $this->post('/api/oauth/introspect', [
        // No token provided
    ], array_merge(
        $this->getBasicAuthHeader(
            $this->introspectionClient->id,
            'introspection-secret'
        ),
        [
            'Accept' => 'application/json',
            'Content-Type' => 'application/x-www-form-urlencoded',
        ]
    ));
    
    $response->assertStatus(422);
    $response->assertJsonValidationErrors(['token']);
}

/**
 * Test introspection with invalid token type hint
 */
public function test_introspection_with_invalid_token_type_hint()
{
    $this->mockJwtParserForAccessToken();
    
    $response = $this->post('/api/oauth/introspect', [
        'token' => 'any-jwt-token',
        'token_type_hint' => 'invalid_hint',
    ], array_merge(
        $this->getBasicAuthHeader(
            $this->introspectionClient->id,
            'introspection-secret'
        ),
        [
            'Accept' => 'application/json',
            'Content-Type' => 'application/x-www-form-urlencoded',
        ]
    ));
    
    $response->assertStatus(422);
    $response->assertJsonValidationErrors(['token_type_hint']);
}
    
    /**
     * Test introspection returns correct scope formatting
     */
    public function test_scope_formatting()
    {
        $this->mockJwtParserForAccessToken();
        
        // Update token with JSON encoded scopes
        $this->accessToken->scopes = json_encode(['read', 'write', 'delete']);
        $this->accessToken->save();
        
        $response = $this->post('/api/oauth/introspect', [
            'token' => 'any-jwt-token',
        ], $this->getBasicAuthHeader(
            $this->introspectionClient->id,
            'introspection-secret'
        ));
        
        $response->assertStatus(200);
        $this->assertEquals('read write delete', $response->json('scope'));
    }
    
    /**
     * Test introspection with plain text client secret (fallback)
     */
    public function test_introspection_with_plain_text_client_secret()
    {
        $this->mockJwtParserForAccessToken();
        
        $plainTextClient = Client::create([
            'owner_id' => $this->user->id,
            'owner_type' => User::class,
            'name' => 'Plain Text Client',
            'secret' => 'plain-text-secret', // Not hashed
            'redirect_uris' => json_encode(['http://localhost/callback']),
            'grant_types' => json_encode(['client_credentials']),
            'revoked' => false,
        ]);
        
        $response = $this->post('/api/oauth/introspect', [
            'token' => 'any-jwt-token',
        ], $this->getBasicAuthHeader(
            $plainTextClient->id,
            'plain-text-secret'
        ));
        
        $response->assertStatus(200);
        $response->assertJson(['active' => true]);
    }
}