<?php

namespace App\Http\Controllers;

use App\Http\Controllers\Controller;
use Illuminate\Http\Request;
use Laravel\Passport\Token;
use Laravel\Passport\RefreshToken;
use Laravel\Passport\Client;
use League\OAuth2\Server\ResourceServer;
use Symfony\Bridge\PsrHttpMessage\Factory\PsrHttpFactory;
use Illuminate\Support\Facades\Log;

class OAuthIntrospectionController extends Controller
{
    protected $resourceServer;
    
    public function __construct(ResourceServer $resourceServer)
    {
        $this->resourceServer = $resourceServer;
    }
    
    /**
     * Handle token introspection request
     * RFC 7662: OAuth 2.0 Token Introspection
     */
    public function introspect(Request $request)
    {
        // Validate required parameters
        $request->validate([
            'token' => 'required|string',
            'token_type_hint' => 'sometimes|in:access_token,refresh_token',
        ]);

        $token = $request->input('token');
        $tokenTypeHint = $request->input('token_type_hint', 'access_token');
        
        // Try to introspect as access token firstF
        $introspection = $this->introspectAccessToken($token);

        // If not found and hint is refresh_token, try as refresh token
        if (!$introspection['active'] && $tokenTypeHint === 'refresh_token') {
            $introspection = $this->introspectRefreshToken($token);
        }

        return response()->json($introspection);
    }

    /**
     * Introspect access token using Passport's ResourceServer
     */
    protected function introspectAccessToken($tokenString)
    {
        try {
            // Create a mock request with the token as Bearer
            $mockRequest = Request::create('/');
            $mockRequest->headers->set('Authorization', 'Bearer ' . $tokenString);
            
            // Use Passport's ResourceServer to validate the token
            $psrRequest = (new PsrHttpFactory)->createRequest($mockRequest);
            $validatedRequest  = $this->resourceServer->validateAuthenticatedRequest($psrRequest);

            // Get token ID from validated request
            $tokenId = $validatedRequest->getAttribute('oauth_access_token_id');
            
            // Find the token in database
            $accessToken = Token::find($tokenId);

            if (!$accessToken || $accessToken->revoked) {
                return ['active' => false];
            }

            // Check if token is expired
            if ($accessToken->expires_at && $accessToken->expires_at->isPast()) {
                return ['active' => false];
            }

            // Get client information
            $client = Client::find($accessToken->client_id);

            // Get user information
            $user = $accessToken->user;

            // Build introspection response according to RFC 7662
            return [
                'active' => true,
                'scope' => $this->formatScopes($accessToken->scopes),
                'client_id' => (string) $accessToken->client_id,
                'username' => $user ? $user->email : null,
                'token_type' => 'access_token',
                'exp' => $accessToken->expires_at ? $accessToken->expires_at->timestamp : null,
                'iat' => $accessToken->created_at ? $accessToken->created_at->timestamp : null,
                'nbf' => $accessToken->created_at ? $accessToken->created_at->timestamp : null,
                'sub' => $accessToken->user_id ? (string) $accessToken->user_id : null,
                'aud' => $client ? (string) $client->id : null,
                'iss' => url('/'),
                'jti' => $tokenId,
                'user_id' => $accessToken->user_id,
                'client_name' => $client ? $client->name : null,
            ];

        } catch (\Exception $e) {
            // Token is invalid
            Log::debug('Token introspection failed', ['error' => $e->getMessage()]);
            return ['active' => false];
        }
    }

    /**
     * Introspect refresh token
     */
    protected function introspectRefreshToken($token)
    {
        // Find refresh token in database
        $refreshToken = RefreshToken::find($token);
        
        if (!$refreshToken || $refreshToken->revoked) {
            return ['active' => false];
        }

        // Check if refresh token is expired
        if ($refreshToken->expires_at && $refreshToken->expires_at->isPast()) {
            return ['active' => false];
        }

        // Get associated access token
        $accessToken = Token::find($refreshToken->access_token_id);
        
        if (!$accessToken || $accessToken->revoked) {
            return ['active' => false];
        }

        // Check if access token is expired
        if ($accessToken->expires_at && $accessToken->expires_at->isPast()) {
            return ['active' => false];
        }

        $client = Client::find($accessToken->client_id);
        $user = $accessToken->user;

        return [
            'active' => true,
            'scope' => $this->formatScopes($accessToken->scopes),
            'client_id' => (string) $accessToken->client_id,
            'username' => $user ? $user->email : null,
            'token_type' => 'refresh_token',
            'exp' => $refreshToken->expires_at ? $refreshToken->expires_at->timestamp : null,
            'iat' => $accessToken->created_at ? $accessToken->created_at->timestamp : null,
            'sub' => $accessToken->user_id ? (string) $accessToken->user_id : null,
            'aud' => $client ? (string) $client->id : null,
            'iss' => url('/'),
            'user_id' => $accessToken->user_id,
            'client_name' => $client ? $client->name : null,
        ];
    }

    /**
     * Format scopes from array to space-separated string
     */
    protected function formatScopes($scopes)
    {
        // If scopes is a JSON string, decode it first
        if (is_string($scopes)) {
            $decoded = json_decode($scopes, true);
            if (json_last_error() === JSON_ERROR_NONE && is_array($decoded)) {
                $scopes = $decoded;
            }
        }
        
        if (is_array($scopes)) {
            return implode(' ', $scopes);
        }
        
        if (is_string($scopes)) {
            return $scopes;
        }
        
        return '';
    }
}