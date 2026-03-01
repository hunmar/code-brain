import { Request, Response } from 'express';

interface ApiResponse<T> {
  data: T;
  status: number;
}

export class UserHandler {
  async getUser(req: Request, res: Response): Promise<void> {
    const userId = req.params.id;
    const user = await this.findUser(userId);
    res.json({ data: user, status: 200 });
  }

  private async findUser(id: string): Promise<any> {
    return { id, name: "test" };
  }
}
