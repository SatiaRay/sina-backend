<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;
use App\Enums\UserRoleInWorkspace;

class WorkspaceInviteRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        return true;
    }

    /**
     * Get the validation rules that apply to the request.
     *
     * @return array<string, \Illuminate\Contracts\Validation\ValidationRule|array<mixed>|string>
     */
    public function rules(): array
    {
        $roles = array_column(UserRoleInWorkspace::cases(), 'value');

        return [
            'email' => 'required|email',
            'role' => 'sometimes|string|in:' . implode(',', $roles)
        ];
    }

    /**
     * Get custom messages for validator errors.
     */
    public function messages(): array
    {
        return [
            'email.required' => 'Email is required',
            'email.email' => 'Please provide a valid email address',
            'role.in' => 'Role must be one of: ' . implode(', ', array_column(UserRoleInWorkspace::cases(), 'value'))
        ];
    }
}