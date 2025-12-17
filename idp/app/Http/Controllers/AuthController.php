<?php

namespace App\Http\Controllers;

use App\Models\User;
use Illuminate\Http\Request;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Hash;
use App\Services\Tenant\CurrentWorkspace;
use Illuminate\Validation\ValidationException;
use Laravel\Passport\Passport;

class AuthController extends Controller
{
    /**
     * Register user
     *
     * @param Request $request
     * @return void
     */
    public function register(Request $request)
    {
        $request->validate([
            'name' => 'required|string|max:255',
            'email' => 'required|string|email|max:255|unique:users',
            'password' => 'required|string|min:8|confirmed',
        ]);

        $user = User::create([
            'name' => $request->name,
            'email' => $request->email,
            'password' => Hash::make($request->password),
        ]);

        $token = $user->createToken('MyAppToken')->accessToken;

        return response()->json(['user' => $user, 'token' => $token], 201);
    }

    /**
     * Login user
     *
     * @param Request $request
     * @return void
     */
    public function login(Request $request): JsonResponse
    {
        $request->validate([
            'email' => 'required|string|email',
            'password' => 'required|string',
            'workspace_id' => 'nullable|string|exists:workspaces,id',
        ]);

        if (!Auth::attempt($request->only('email', 'password'))) {
            throw ValidationException::withMessages([
                'email' => ['Invalid credentials.'],
            ]);
        }

        $user = Auth::user();

        $currentWorkspaceId = $request->input('workspace_id') ?? $user->primary_workspace_id;

        Passport::tokensCan([
           "workspace:{$currentWorkspaceId}"  => 'View workspace details',
        ]);

        $token = $user->createToken('SSO', ["workspace:{$currentWorkspaceId}"])->accessToken;

        return response()->json(['user' => $user, 'token' => $token]);
    }

    /**
     * Logout user
     * @param \Illuminate\Http\Request $request
     * @return \Illuminate\Http\JsonResponse
     */
    public function logout(Request $request)
    {
        $request->user()->token()->revoke();

        return response()->json(['message' => 'Successfully logged out']);
    }
}