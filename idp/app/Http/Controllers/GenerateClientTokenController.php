<?php

namespace App\Http\Controllers;

use App\Http\Requests\GenerateClientTokenRequest;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;

class GenerateClientTokenController extends Controller
{
    /**
     * Handle the incoming request.
     * 
     * Issues client token then response back
     */
    public function __invoke(GenerateClientTokenRequest $request)
    {
        $response = Http::asForm()->post('http://idp/oauth/token', [
            'grant_type' => 'client_credentials',
            'client_id' => $request->input('client_id'),
            'client_secret' => $request->input('client_secret'),
            'scope' => '*',
        ]);

        if(!$response->ok())
            return response(['msg' => 'operation failed !'], 500);

        return response()->json([
            'token' => $response->json()['access_token']
        ]);
    }
}