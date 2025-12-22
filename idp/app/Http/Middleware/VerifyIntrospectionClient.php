<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Laravel\Passport\Client;

class VerifyIntrospectionClient
{
    public function handle(Request $request, Closure $next)
    {
        // Get client credentials
        $clientId = $request->getUser();
        $clientSecret = $request->getPassword();

        if (!$clientId || !$clientSecret) {
            $clientId = $request->input('client_id');
            $clientSecret = $request->input('client_secret');
        }

        if (!$clientId || !$clientSecret) {
            return response()->json([
                'error' => 'invalid_client',
                'error_description' => 'Client authentication failed'
            ], 401);
        }

        // Find active client
        $client = Client::where('id', $clientId)
            ->where('revoked', false)
            ->first();

        if (!$client) {
            return response()->json([
                'error' => 'invalid_client',
                'error_description' => 'Client not found or revoked'
            ], 401);
        }

        // Verify secret
        if (!password_verify($clientSecret, $client->secret)) {
            // Fallback for plain text (not recommended)
            if (!hash_equals($client->secret, $clientSecret)) {
                return response()->json([
                    'error' => 'invalid_client',
                    'error_description' => 'Invalid client credentials'
                ], 401);
            }
        }

        // Attach client to request for controller use
        $request->attributes->set('introspection_client', $client);

        return $next($request);
    }
}