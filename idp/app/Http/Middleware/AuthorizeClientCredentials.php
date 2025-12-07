<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Laravel\Passport\Client;
use Symfony\Component\HttpFoundation\Response;
use Illuminate\Support\Facades\Hash;

class AuthorizeClientCredentials
{
    /**
     * Handle an incoming request.
     */
    public function handle(Request $request, Closure $next): Response
    {
        if (!$request->has(['client_id', 'client_secret'])) {
            return response(['msg' => 'Credentials are required!'], 403);
        }

        $client = Client::where('id', $request->input('client_id'))
            ->where('revoked', false)
            ->first();

        if (!$client) {
            return response(['msg' => 'Invalid client ID.'], 403);
        }

        // Validate secret using Hash::check
        if (!Hash::check($request->input('client_secret'), $client->secret)) {
            return response(['msg' => 'Invalid client secret.'], 403);
        }

        return $next($request);
    }
}