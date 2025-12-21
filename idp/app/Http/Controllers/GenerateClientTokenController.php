<?php

namespace App\Http\Controllers;

use App\Http\Requests\GenerateClientTokenRequest;
use GuzzleHttp\Psr7\Response;
use League\OAuth2\Server\AuthorizationServer;
use Psr\Http\Message\ServerRequestInterface;
use Exception;
use League\OAuth2\Server\Exception\OAuthServerException;

class GenerateClientTokenController extends Controller
{
    /**
     * Handle the incoming request.
     * 
     * Issues client token then response back
     */
    public function __invoke(GenerateClientTokenRequest $request)
    {
        try {
            $server = resolve(AuthorizationServer::class);

            $psr = app(ServerRequestInterface::class)
                ->withParsedBody([
                    'grant_type' => 'client_credentials',
                    'client_id' => $request->client_id,
                    'client_secret' => $request->client_secret,
                    'scope' => '*',
                ]);

            $response = $server->respondToAccessTokenRequest($psr, new Response());

            return response()->json([
                'token' => json_decode((string) $response->getBody(), true)['access_token']
            ]);
            
        } catch (OAuthServerException $exception) {
            // Handle OAuth specific exceptions
            return response()->json([
                'msg' => 'operation failed !'
            ], 500);
            
        } catch (Exception $exception) {
            // Handle any other exceptions
            return response()->json([
                'msg' => 'operation failed !'
            ], 500);
        }
    }
}