<?php

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use App\Http\Controllers\AuthController;
use App\Http\Controllers\Api\UserController;
use App\Http\Middleware\AuthorizeClientCredentials;
use App\Http\Controllers\GenerateClientTokenController;
use App\Http\Controllers\Api\OAuthIntrospectionController;
use App\Http\Middleware\VerifyIntrospectionClient;

Route::get('/user', function (Request $request) {
    return $request->user();
})->middleware('auth:api');

/**
 * Client -> Machine login and register endpoints
 */
Route::post('/register', [AuthController::class, 'register']);
Route::post('/login', [AuthController::class, 'login']);

/**
 * Machine -> Machine auth endpoints
 */
Route::name('internal.')->prefix('/internal')->group(function () {
    Route::post('/client-token', GenerateClientTokenController::class)->middleware([AuthorizeClientCredentials::class])->name('client-token');
});

/**
 * Protected routes
 */
Route::middleware('auth:api')->group(function () {
    Route::post('/logout', [AuthController::class, 'logout']);
    Route::post('/switch-workspace', [AuthController::class, 'switchWorkspace']);

    Route::get('/me/workspaces', [UserController::class, 'getUserWorkspaces']);
    Route::post('me/workspaces/{workspace}/switch', [UserController::class, 'switchWorkspace']);

    Route::apiResource('/workspaces', App\Http\Controllers\Api\WorkspaceController::class);
    Route::post('/workspaces/{workspace}/invite', [App\Http\Controllers\Api\WorkspaceController::class, 'invite']);
    Route::delete('/workspaces/{workspace}/members/{user}', [App\Http\Controllers\Api\WorkspaceController::class, 'removeMember'] );
    Route::post('/workspaces/{workspace}/leave', [App\Http\Controllers\Api\WorkspaceController::class, 'leave'] );
});


/**
 * Protected introspection endpoint (recommended)
 */
Route::middleware([VerifyIntrospectionClient::class])->post('/oauth/introspect', 
    [OAuthIntrospectionController::class, 'introspect']);