<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Laravel\Passport\Token;
use Laravel\Passport\RefreshToken;
use Laravel\Passport\Client;
use Lcobucci\JWT\Encoding\JoseEncoder;
use Lcobucci\JWT\Token\Parser;
use Carbon\Carbon;
use Illuminate\Support\Facades\Log;

class OAuthIntrospectionController extends Controller
{
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
        
        // Verify client authentication first (for protected endpoint)
        $client = $this->verifyClient($request);
        if (!$client) {
            return response()->json(['error' => 'invalid_client'], 401);
        }

        // Try to introspect as access token first
        $introspection = $this->introspectAccessToken($token);
        
        // If not found and hint is refresh_token, try as refresh token
        if (!$introspection['active'] && $tokenTypeHint === 'refresh_token') {
            $introspection = $this->introspectRefreshToken($token);
        }

        return response()->json($introspection);
    }

    /**
     * Introspect access token
     */
    protected function introspectAccessToken($token)
    {
        try {
            // Parse JWT token
            $parser = new Parser(new JoseEncoder());
            $parsedToken = $parser->parse($token);
            
            // Get token ID from JWT claims
            $tokenId = $parsedToken->claims()->get('jti');
            
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
            // Token is not JWT or invalid
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
        if (is_array($scopes)) {
            return implode(' ', $scopes);
        }
        
        if (is_string($scopes)) {
            return $scopes;
        }
        
        return '';
    }

    /**
     * Verify client authentication
     */
    protected function verifyClient(Request $request)
    {
        $credentials = $this->getClientCredentials($request);
        
        if (!$credentials) {
            return null;
        }

        // Find the client
        $client = Client::where('id', $credentials['client_id'])
            ->where('revoked', false)
            ->first();

        // Verify client secret
        if (!$client || !$this->verifySecret($client->secret, $credentials['client_secret'])) {
            return null;
        }

        // Optionally, check if client is allowed to use introspection
        // You can add a column to oauth_clients table or use client metadata
        // if (!$client->can_introspect) {
        //     return null;
        // }

        return $client;
    }

    /**
     * Get client credentials from request
     */
    protected function getClientCredentials(Request $request)
    {
        // Check Authorization header (Basic auth)
        if ($request->header('Authorization')) {
            $auth = $request->header('Authorization');
            if (strpos($auth, 'Basic ') === 0) {
                $credentials = base64_decode(substr($auth, 6));
                list($clientId, $clientSecret) = explode(':', $credentials, 2);
                return [
                    'client_id' => $clientId,
                    'client_secret' => $clientSecret,
                ];
            }
        }

        // Check request body parameters
        if ($request->filled('client_id') && $request->filled('client_secret')) {
            return [
                'client_id' => $request->input('client_id'),
                'client_secret' => $request->input('client_secret'),
            ];
        }

        return null;
    }

    /**
     * Verify client secret (handles hashed secrets)
     */
    protected function verifySecret($storedSecret, $providedSecret)
    {
        // If secret is hashed with password_hash()
        if (password_verify($providedSecret, $storedSecret)) {
            return true;
        }

        // For plain text secrets (not recommended)
        if (hash_equals($storedSecret, $providedSecret)) {
            return true;
        }

        return false;
    }
}